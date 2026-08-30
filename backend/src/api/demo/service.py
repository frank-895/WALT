import asyncio
import contextlib
import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from api.demo.browser import BrowserController
from api.demo.models import (
    BrowserAction,
    BrowserActionResult,
    DemoBrief,
    DemoConflictError,
    DemoNotFoundError,
    DemoNotReadyError,
    DemoSessionCreated,
    DemoSessionState,
    DemoStatus,
    ObserveAction,
    VoiceAnswer,
)
from api.demo.providers import SandboxProvider
from api.demo.seed import generate_seed
from api.demo.voice import VoiceRuntime
from api.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class DemoSession:
    """Private, process-local state for one disposable demo."""

    id: str
    expires_at: datetime
    status: DemoStatus = "provisioning"
    view_url: str | None = None
    error: str | None = None
    sandbox: Any = None
    controller: BrowserController | None = None
    provision_task: asyncio.Task[None] | None = None
    prepare_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    seed_digest: str | None = None
    initial_observation: BrowserActionResult | None = None


class DemoService:
    """Coordinate disposable Daytona sessions and their Realtime sidebands."""

    def __init__(
        self,
        settings: Settings,
        sandboxes: SandboxProvider,
        voice: VoiceRuntime,
    ) -> None:
        """Create the application service.

        Args:
            settings: Validated application settings.
            sandboxes: Daytona lifecycle provider.
            voice: Realtime signaling and sideband runtime.
        """
        self._settings = settings
        self._sandboxes = sandboxes
        self._voice = voice
        self._sessions: dict[str, DemoSession] = {}
        self._registry_lock = asyncio.Lock()
        self._sweeper_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start automatic expiry cleanup."""
        self._sweeper_task = asyncio.create_task(
            self._sweep_expired(), name="demo-expiry-sweeper"
        )

    async def close(self) -> None:
        """Delete active sandboxes and release provider resources."""
        if self._sweeper_task:
            self._sweeper_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sweeper_task
        async with self._registry_lock:
            session_ids = list(self._sessions)
        await asyncio.gather(*(self.delete(session_id) for session_id in session_ids))
        await self._voice.close()
        await self._sandboxes.close()

    async def create(self) -> DemoSessionCreated:
        """Begin provisioning one disposable sandbox.

        Returns:
            Opaque session metadata.
        """
        session_id = secrets.token_urlsafe(24)
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self._settings.demo_ttl_seconds
        )
        session = DemoSession(id=session_id, expires_at=expires_at)
        async with self._registry_lock:
            self._sessions[session_id] = session
        session.provision_task = asyncio.create_task(
            self._provision(session), name=f"provision-{session_id}"
        )
        return DemoSessionCreated(
            id=session_id,
            status="provisioning",
            expires_at=expires_at,
        )

    async def get(self, session_id: str) -> DemoSessionState:
        """Return public state for a live demo.

        Args:
            session_id: Opaque demo identifier.

        Returns:
            Current session status.

        Raises:
            DemoNotFoundError: The session is absent or expired.
        """
        session = await self._live_session(session_id)
        return DemoSessionState(
            id=session.id,
            status=session.status,
            expires_at=session.expires_at,
            view_url=session.view_url if session.status == "ready" else None,
            error=session.error,
        )

    async def answer_offer(self, session_id: str, sdp_offer: str) -> VoiceAnswer:
        """Attach voice and tools to one browser WebRTC call.

        Args:
            session_id: Opaque demo identifier.
            sdp_offer: Browser-generated SDP offer.

        Returns:
            OpenAI's SDP answer and call identifier.
        """
        await self._live_session(session_id)
        return await self._voice.answer_offer(session_id, sdp_offer, self)

    async def prepare(self, session_id: str, brief: DemoBrief) -> BrowserActionResult:
        """Generate data, seed Atomic, open Chromium, and observe it.

        Args:
            session_id: Opaque demo identifier.
            brief: Compact visitor context.

        Returns:
            Initial accessibility state and screenshot.

        Raises:
            DemoConflictError: Different data already prepared the demo.
            DemoNotReadyError: Sandbox provisioning or startup failed.
        """
        session = await self._live_session(session_id)
        digest = hashlib.sha256(brief.model_dump_json().encode()).hexdigest()
        async with session.prepare_lock:
            if session.seed_digest:
                if session.seed_digest != digest:
                    raise DemoConflictError(
                        "This demo is already prepared with different data"
                    )
                if session.initial_observation:
                    return session.initial_observation
            if session.provision_task:
                await session.provision_task
            if session.status == "failed" or not session.sandbox:
                raise DemoNotReadyError(
                    session.error or "The demo sandbox could not be prepared"
                )
            session.status = "preparing"
            session.error = None
            try:
                await self._sandboxes.upload_seed(session.sandbox, generate_seed(brief))
                await self._sandboxes.reload_demo(session.sandbox)
                controller = self._sandboxes.browser_controller(session.sandbox)
                observation = await controller.execute(ObserveAction(action="observe"))
            except Exception as error:
                session.status = "onboarding"
                logger.warning(
                    "demo_prepare_failed",
                    extra={
                        "demo_session_id": session.id,
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                    },
                )
                raise DemoNotReadyError(
                    "Atomic was not ready yet; try prepare_demo again."
                ) from error
            session.controller = controller
            session.seed_digest = digest
            session.initial_observation = observation
            session.status = "ready"
            logger.info(
                "demo_prepared",
                extra={"demo_session_id": session.id},
            )
            return observation

    async def browser_action(
        self, session_id: str, action: BrowserAction
    ) -> BrowserActionResult:
        """Execute one validated operation against a ready Atomic browser.

        Args:
            session_id: Opaque demo identifier.
            action: One of the six allowed actions.

        Returns:
            Fresh browser state and screenshot.

        Raises:
            DemoNotReadyError: Atomic is not ready for actions.
        """
        session = await self._live_session(session_id)
        if session.status != "ready" or not session.controller:
            raise DemoNotReadyError("Prepare the demo before using browser tools")
        return await session.controller.execute(action)

    async def delete(self, session_id: str) -> None:
        """Idempotently purge a session and delete its sandbox.

        Args:
            session_id: Opaque demo identifier.
        """
        async with self._registry_lock:
            session = self._sessions.pop(session_id, None)
        if not session:
            return
        await self._voice.close_session(session_id)
        current_task = asyncio.current_task()
        if (
            session.provision_task
            and session.provision_task is not current_task
            and not session.provision_task.done()
        ):
            session.provision_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await session.provision_task
        if session.sandbox:
            try:
                await self._sandboxes.delete(session.sandbox)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "sandbox_delete_failed", extra={"demo_session_id": session.id}
                )

    async def _provision(self, session: DemoSession) -> None:
        """Create the sandbox, desktop, and signed noVNC preview.

        Args:
            session: Newly registered private session state.
        """
        try:
            session.sandbox = await self._sandboxes.create(session.id)
            await self._sandboxes.start_desktop(session.sandbox)
            await self._sandboxes.start_demo(session.sandbox)
            remaining_seconds = max(
                1, int((session.expires_at - datetime.now(UTC)).total_seconds())
            )
            session.view_url = await self._sandboxes.create_view_url(
                session.sandbox, remaining_seconds
            )
            session.status = "onboarding"
        except asyncio.CancelledError:
            if session.sandbox:
                with contextlib.suppress(Exception):
                    await self._sandboxes.delete(session.sandbox)
                    session.sandbox = None
            raise
        except Exception as error:  # noqa: BLE001
            session.status = "failed"
            session.error = "The demo sandbox could not be started."
            logger.warning(
                "demo_provision_failed",
                extra={
                    "demo_session_id": session.id,
                    "error_type": type(error).__name__,
                },
            )

    async def _live_session(self, session_id: str) -> DemoSession:
        """Resolve a non-expired private session.

        Args:
            session_id: Opaque demo identifier.

        Returns:
            Live private session state.

        Raises:
            DemoNotFoundError: The session is absent or expired.
        """
        async with self._registry_lock:
            session = self._sessions.get(session_id)
        if not session:
            raise DemoNotFoundError("Demo session not found")
        if session.expires_at <= datetime.now(UTC):
            await self.delete(session_id)
            raise DemoNotFoundError("Demo session not found")
        return session

    async def _sweep_expired(self) -> None:
        """Continuously delete sessions after their hard TTL."""
        while True:
            await asyncio.sleep(self._settings.expiry_sweep_seconds)
            now = datetime.now(UTC)
            async with self._registry_lock:
                expired_ids = [
                    session_id
                    for session_id, session in self._sessions.items()
                    if session.expires_at <= now
                ]
            if expired_ids:
                await asyncio.gather(
                    *(self.delete(session_id) for session_id in expired_ids)
                )
