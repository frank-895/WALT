import json
import math
from typing import Any, Protocol

from daytona import (
    AsyncDaytona,
    AsyncSandbox,
    CreateSandboxFromSnapshotParams,
    DaytonaConfig,
    ScreenshotOptions,
)

from api.demo.browser import BrowserController, ProcessResult, ScreenshotResult
from api.demo.browser_harness import BROWSER_ACTION_COMMAND, RELOAD_DEMO_COMMAND
from api.settings import Settings


class ProviderConfigurationError(Exception):
    """A required external provider setting is absent."""


class SandboxProvider(Protocol):
    """Lifecycle operations required for disposable demo sandboxes."""

    async def create(self, session_id: str) -> Any:
        """Create a sandbox from the prepared snapshot."""
        ...

    async def start_desktop(self, sandbox: Any) -> None:
        """Start and verify Daytona Computer Use."""
        ...

    async def create_view_url(self, sandbox: Any, expires_in_seconds: int) -> str:
        """Create a signed noVNC preview URL."""
        ...

    async def upload_seed(self, sandbox: Any, seed: dict[str, Any]) -> None:
        """Upload the finalized Atomic seed."""
        ...

    async def start_demo(self, sandbox: Any) -> None:
        """Start Chromium and wait for Atomic readiness."""
        ...

    async def reload_demo(self, sandbox: Any) -> None:
        """Reload Atomic after uploading the visitor seed."""
        ...

    def browser_controller(self, sandbox: Any) -> BrowserController:
        """Create the safe browser controller for a ready sandbox."""
        ...

    async def delete(self, sandbox: Any) -> None:
        """Delete the sandbox."""
        ...

    async def close(self) -> None:
        """Release provider resources."""
        ...


class DaytonaBrowserSandbox:
    """Expose fixed browser and screenshot operations."""

    def __init__(self, sandbox: AsyncSandbox) -> None:
        """Wrap a Daytona sandbox.

        Args:
            sandbox: Ready Daytona sandbox.
        """
        self._sandbox = sandbox

    async def run_browser_action(self, request: str, timeout: int) -> ProcessResult:
        """Execute the fixed Browser Use program with a base64 JSON request.

        Args:
            request: Base64-encoded validated action JSON.
            timeout: Operation deadline in seconds.

        Returns:
            Daytona's process result.
        """
        return await self._sandbox.process.exec(
            BROWSER_ACTION_COMMAND,
            env={"WALT_BROWSER_REQUEST": request},
            timeout=timeout,
        )

    async def take_screenshot(self, quality: int, scale: float) -> ScreenshotResult:
        """Capture a compressed JPEG from the visible Daytona desktop.

        Args:
            quality: JPEG quality from 0 to 100.
            scale: Fractional screenshot scale.

        Returns:
            Daytona's screenshot response.
        """
        return await self._sandbox.computer_use.screenshot.take_compressed(
            ScreenshotOptions(
                fmt="jpeg", quality=quality, scale=scale, show_cursor=True
            )
        )


class DaytonaSandboxProvider:
    """Provision and destroy prepared Atomic sandboxes with Daytona."""

    def __init__(self, settings: Settings, client: AsyncDaytona | None = None) -> None:
        """Create a Daytona sandbox provider.

        Args:
            settings: Validated application settings.
            client: Optional Daytona client for tests.
        """
        self._settings = settings
        self._client = client
        self._owns_client = client is None

    def _daytona(self) -> AsyncDaytona:
        """Return a lazily configured Daytona client.

        Returns:
            The reusable asynchronous Daytona client.

        Raises:
            ProviderConfigurationError: Daytona settings are incomplete.
        """
        if self._client:
            return self._client
        if not self._settings.daytona_api_key or not self._settings.daytona_snapshot:
            raise ProviderConfigurationError(
                "WALT_DAYTONA_API_KEY and WALT_DAYTONA_SNAPSHOT are required"
            )
        self._client = AsyncDaytona(
            DaytonaConfig(
                api_key=self._settings.daytona_api_key.get_secret_value(),
                api_url=self._settings.daytona_api_url,
            )
        )
        return self._client

    async def create(self, session_id: str) -> AsyncSandbox:
        """Create an ephemeral sandbox from the prepared Atomic snapshot.

        Args:
            session_id: Opaque application session identifier.

        Returns:
            The created Daytona sandbox.
        """
        if not self._settings.daytona_snapshot:
            raise ProviderConfigurationError("WALT_DAYTONA_SNAPSHOT is required")
        ttl_minutes = math.ceil(self._settings.demo_ttl_seconds / 60)
        params = CreateSandboxFromSnapshotParams(
            name=f"walt-{session_id[:12]}",
            snapshot=self._settings.daytona_snapshot,
            labels={"application": "walt", "session": session_id},
            ephemeral=True,
            ttl_minutes=ttl_minutes,
        )
        return await self._daytona().create(params)

    async def start_desktop(self, sandbox: AsyncSandbox) -> None:
        """Start and verify Daytona's graphical desktop.

        Args:
            sandbox: Newly created Daytona sandbox.
        """
        await sandbox.computer_use.start()
        await sandbox.computer_use.get_status()

    async def create_view_url(
        self, sandbox: AsyncSandbox, expires_in_seconds: int
    ) -> str:
        """Create a signed noVNC preview URL.

        Args:
            sandbox: Active Daytona sandbox.
            expires_in_seconds: Preview credential lifetime.

        Returns:
            Signed preview URL safe to expose to the browser.
        """
        preview = await sandbox.create_signed_preview_url(
            self._settings.novnc_port, expires_in_seconds=expires_in_seconds
        )
        return preview.url

    async def upload_seed(self, sandbox: AsyncSandbox, seed: dict[str, Any]) -> None:
        """Upload finalized Atomic data without persisting it in WALT.

        Args:
            sandbox: Active Daytona sandbox.
            seed: Final Atomic database object.
        """
        contents = json.dumps(seed, separators=(",", ":"), ensure_ascii=False).encode()
        await sandbox.fs.upload_file(contents, self._settings.seed_path)

    async def start_demo(self, sandbox: AsyncSandbox) -> None:
        """Run the preinstalled Chromium and Atomic readiness command.

        Args:
            sandbox: Seeded Daytona sandbox.

        Raises:
            RuntimeError: The image startup command fails.
        """
        result = await sandbox.process.exec(self._settings.start_command, timeout=60)
        if result.exit_code != 0:
            raise RuntimeError("Atomic startup command failed")

    async def reload_demo(self, sandbox: AsyncSandbox) -> None:
        """Reload the prewarmed Atomic tab with the visitor seed.

        Args:
            sandbox: Seeded Daytona sandbox with Chromium already running.

        Raises:
            RuntimeError: Atomic does not finish loading the tailored seed.
        """
        result = await sandbox.process.exec(RELOAD_DEMO_COMMAND, timeout=20)
        if result.exit_code != 0:
            raise RuntimeError("Atomic seed reload failed")

    def browser_controller(self, sandbox: AsyncSandbox) -> BrowserController:
        """Create the safe browser adapter for one Chromium session.

        Args:
            sandbox: Ready Daytona sandbox.

        Returns:
            A serialized safe browser controller.
        """
        return BrowserController(
            DaytonaBrowserSandbox(sandbox),
            atomic_origin=self._settings.atomic_origin,
            timeout_seconds=self._settings.browser_action_timeout_seconds,
            screenshot_quality=self._settings.screenshot_quality,
            screenshot_scale=self._settings.screenshot_scale,
        )

    async def delete(self, sandbox: AsyncSandbox) -> None:
        """Permanently delete one disposable sandbox.

        Args:
            sandbox: Daytona sandbox to delete.
        """
        await self._daytona().delete(sandbox, wait=True)

    async def close(self) -> None:
        """Close the owned Daytona client."""
        if self._owns_client and self._client:
            await self._client.close()
