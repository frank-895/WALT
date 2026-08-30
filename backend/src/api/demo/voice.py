import asyncio
import base64
import contextlib
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic_ai import Agent, BinaryContent, ModelRetry, RunContext, ToolReturn
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.realtime import WebRTCSession
from pydantic_ai.realtime.openai import (
    OpenAIRealtimeModel,
    OpenAIRealtimeModelSettings,
)

from api.demo.browser import BrowserActionError
from api.demo.models import (
    BrowserAction,
    BrowserActionResult,
    BrowserKey,
    ClickAction,
    CompanyName,
    DemoBrief,
    DemoConflictError,
    DemoIndustry,
    DemoNotFoundError,
    DemoNotReadyError,
    DemoPriorities,
    DemoTeamSize,
    FillAction,
    FillValue,
    KeyAction,
    ObserveAction,
    Reference,
    ScrollAction,
    ScrollDelta,
    VisitorName,
    VoiceAnswer,
    WaitAction,
    WaitMilliseconds,
)
from api.demo.providers import ProviderConfigurationError
from api.settings import Settings

logger = logging.getLogger(__name__)

SALESPERSON_PROMPT = """You are Walt, a concise voice-first salesperson giving a live Atomic CRM demo. The visitor can hear you and sees a live transcript of each thing you say.

Start immediately by asking exactly: "Tell me briefly about your company." This is the entire onboarding. Do not add a welcome, combine it with another question, or ask any follow-up questions. After the visitor answers, infer the company name, broad industry, approximate team size, and one to three useful CRM priorities from that single answer. When a detail is missing, use a reasonable generic value instead of asking for clarification. Do not collect sensitive or unnecessary personal data.

After the visitor's first substantive answer, briefly say you have enough to tailor the demo and call prepare_demo immediately in that same response. Never end or pause between that sentence and the tool call. It creates a complete fictional dataset, so omit unknown arguments and use reasonable fictional defaults instead of inventing every CRM record yourself. Never say the demo is being prepared unless you actually call prepare_demo. Never mention sandboxes, seeding, browser startup, tools, or implementation details. When preparation succeeds, tell the visitor their demo is ready and move straight into the demonstration.

Once Atomic is ready, demonstrate conversationally instead of following a fixed tour. Before each action, briefly explain the customer benefit. Take exactly one granular browser action, then inspect the returned controls and screenshot before deciding what to do next. Element refs expire after every action. Never guess a ref or claim a write succeeded just because a tool ran. Open dropdowns, observe their options, and only then choose. Stay entirely inside Atomic CRM."""


class DemoTools(Protocol):
    """Application operations available to the voice agent."""

    async def prepare(self, session_id: str, brief: DemoBrief) -> BrowserActionResult:
        """Seed and open Atomic for one session."""
        ...

    async def browser_action(
        self, session_id: str, action: BrowserAction
    ) -> BrowserActionResult:
        """Run one safe browser action."""
        ...


class VoiceRuntime(Protocol):
    """Realtime signaling and sideband lifecycle used by DemoService."""

    async def answer_offer(
        self, session_id: str, sdp_offer: str, demo_tools: DemoTools
    ) -> VoiceAnswer:
        """Answer a browser WebRTC offer and attach its tool sideband."""
        ...

    async def close_session(self, session_id: str) -> None:
        """Stop one session's sideband connection."""
        ...

    async def close(self) -> None:
        """Stop every sideband connection."""
        ...


@dataclass(frozen=True)
class VoiceDependencies:
    """Per-call dependencies available to PydanticAI tools."""

    session_id: str
    demo_tools: DemoTools


@dataclass
class VoiceCall:
    """One live WebRTC call and its server-side sideband task."""

    realtime: Any
    provider_session: WebRTCSession
    task: asyncio.Task[None] | None = None
    attached: asyncio.Event = field(default_factory=asyncio.Event)
    attach_error: BaseException | None = None


agent = Agent(
    deps_type=VoiceDependencies,
    instructions=SALESPERSON_PROMPT,
    retries=2,
)


@agent.tool(retries=2, sequential=True)
async def prepare_demo(
    ctx: RunContext[VoiceDependencies],
    company_name: CompanyName | None = None,
    priorities: DemoPriorities | None = None,
    industry: DemoIndustry = "other",
    team_size: DemoTeamSize = "11-50",
    visitor_name: VisitorName | None = None,
) -> ToolReturn:
    """Finish onboarding by creating fictional CRM data and opening Atomic.

    Args:
        ctx: Active voice session context.
        company_name: Visitor's company name when they shared it.
        priorities: One to three CRM outcomes inferred from the conversation.
        industry: Broad company industry.
        team_size: Approximate company team size.
        visitor_name: Optional visitor name when they offered it.

    Returns:
        Fresh Atomic controls and an exact screenshot.
    """
    brief = DemoBrief(
        company_name=company_name or "Summit Solutions",
        priorities=priorities or ["pipeline-visibility", "follow-up"],
        industry=industry,
        team_size=team_size,
        visitor_name=visitor_name,
    )
    return await _run_tool(ctx, ctx.deps.demo_tools.prepare(ctx.deps.session_id, brief))


@agent.tool(retries=2, sequential=True)
async def browser_observe(ctx: RunContext[VoiceDependencies]) -> ToolReturn:
    """Refresh the current Atomic controls and screenshot."""
    return await _run_browser_action(ctx, ObserveAction(action="observe"))


@agent.tool(retries=2, sequential=True)
async def browser_click(
    ctx: RunContext[VoiceDependencies], ref: Reference, generation: int
) -> ToolReturn:
    """Click one enabled control from the latest observation."""
    return await _run_browser_action(
        ctx, ClickAction(action="click", ref=ref, generation=generation)
    )


@agent.tool(retries=2, sequential=True)
async def browser_fill(
    ctx: RunContext[VoiceDependencies],
    ref: Reference,
    generation: int,
    value: FillValue,
) -> ToolReturn:
    """Replace the value of one editable control from the latest observation."""
    return await _run_browser_action(
        ctx, FillAction(action="fill", ref=ref, generation=generation, value=value)
    )


@agent.tool(retries=2, sequential=True)
async def browser_key(
    ctx: RunContext[VoiceDependencies], key: BrowserKey
) -> ToolReturn:
    """Press one allowed keyboard key."""
    return await _run_browser_action(ctx, KeyAction(action="key", key=key))


@agent.tool(retries=2, sequential=True)
async def browser_scroll(
    ctx: RunContext[VoiceDependencies], delta_y: ScrollDelta
) -> ToolReturn:
    """Scroll Atomic vertically by a bounded pixel amount."""
    return await _run_browser_action(
        ctx, ScrollAction(action="scroll", delta_y=delta_y)
    )


@agent.tool(retries=2, sequential=True)
async def browser_wait(
    ctx: RunContext[VoiceDependencies], milliseconds: WaitMilliseconds = 500
) -> ToolReturn:
    """Wait briefly for Atomic to update, then observe again."""
    return await _run_browser_action(
        ctx, WaitAction(action="wait", milliseconds=milliseconds)
    )


async def _run_browser_action(
    ctx: RunContext[VoiceDependencies], action: BrowserAction
) -> ToolReturn:
    """Run one browser action through the current demo dependency."""
    return await _run_tool(
        ctx, ctx.deps.demo_tools.browser_action(ctx.deps.session_id, action)
    )


async def _run_tool(
    ctx: RunContext[VoiceDependencies],
    operation: Any,
) -> ToolReturn:
    """Convert one demo operation into a validated multimodal tool result."""
    try:
        result = await operation
    except (
        BrowserActionError,
        DemoConflictError,
        DemoNotFoundError,
        DemoNotReadyError,
    ) as error:
        raise ModelRetry(str(error)) from error
    return _tool_result(result)


def _tool_result(result: BrowserActionResult) -> ToolReturn:
    """Attach the exact post-action screenshot to compact browser state."""
    screenshot = result.screenshot
    if screenshot.startswith("data:"):
        screenshot = screenshot.partition(",")[2]
    try:
        image = base64.b64decode(screenshot, validate=True)
    except ValueError as error:
        raise ModelRetry("The screenshot was invalid; observe Atomic again.") from error
    state = result.model_dump(exclude={"screenshot"})
    return ToolReturn(
        return_value=state,
        content=[BinaryContent(data=image, media_type="image/jpeg")],
    )


class PydanticVoiceRuntime:
    """Run OpenAI Realtime WebRTC calls through a PydanticAI sideband."""

    def __init__(self, settings: Settings) -> None:
        """Create a lazily configured voice runtime.

        Args:
            settings: Validated application settings.
        """
        self._settings = settings
        self._calls: dict[str, VoiceCall] = {}
        self._calls_lock = asyncio.Lock()
        self._model: OpenAIRealtimeModel | None = None
        self._provider: OpenAIProvider | None = None

    async def answer_offer(
        self, session_id: str, sdp_offer: str, demo_tools: DemoTools
    ) -> VoiceAnswer:
        """Relay SDP to OpenAI and attach the PydanticAI tool loop.

        Args:
            session_id: Opaque demo identifier.
            sdp_offer: Browser-generated WebRTC offer.
            demo_tools: Session-scoped application operations.

        Returns:
            SDP answer and OpenAI call identifier.

        Raises:
            DemoConflictError: Voice is already attached to the session.
            ProviderConfigurationError: The OpenAI key is absent.
            RuntimeError: The sideband cannot attach.
        """
        async with self._calls_lock:
            if session_id in self._calls:
                raise DemoConflictError("Voice is already connected to this demo")
        realtime = agent.realtime(
            self._openai_model(),
            deps=VoiceDependencies(session_id=session_id, demo_tools=demo_tools),
            model_settings=OpenAIRealtimeModelSettings(
                openai_voice=self._settings.openai_realtime_voice,
                input_transcription_model="auto",
                output_modality="audio",
                parallel_tool_calls=False,
            ),
            conversation_id=session_id,
        )
        answer = await realtime.answer_webrtc_offer(sdp_offer)
        answer_sdp = normalize_sdp(answer.sdp)
        call = VoiceCall(realtime=realtime, provider_session=answer.session)
        async with self._calls_lock:
            if session_id in self._calls:
                raise DemoConflictError("Voice is already connected to this demo")
            self._calls[session_id] = call
        call.task = asyncio.create_task(
            self._run_sideband(session_id, call),
            name=f"realtime-sideband-{session_id}",
        )
        try:
            await asyncio.wait_for(call.attached.wait(), timeout=10)
        except TimeoutError:
            await self.close_session(session_id)
            raise RuntimeError("Timed out attaching the Realtime sideband") from None
        except asyncio.CancelledError:
            await self.close_session(session_id)
            raise
        if call.attach_error:
            await self.close_session(session_id)
            raise RuntimeError(
                "The Realtime sideband could not attach"
            ) from call.attach_error
        return VoiceAnswer(sdp=answer_sdp, call_id=answer.session.call_id)

    async def close_session(self, session_id: str) -> None:
        """Stop one sideband connection.

        Args:
            session_id: Opaque demo identifier.
        """
        async with self._calls_lock:
            call = self._calls.pop(session_id, None)
        if not call:
            return
        if call.task:
            call.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await call.task
        if self._provider:
            try:
                await self._provider.client.realtime.calls.hangup(
                    call.provider_session.call_id
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "realtime_hangup_failed",
                    extra={
                        "demo_session_id": session_id,
                        "realtime_call_id": call.provider_session.call_id,
                    },
                )

    async def close(self) -> None:
        """Stop every active sideband connection."""
        async with self._calls_lock:
            session_ids = list(self._calls)
        await asyncio.gather(*(self.close_session(item) for item in session_ids))

    def _openai_model(self) -> OpenAIRealtimeModel:
        """Return the lazily configured OpenAI Realtime model."""
        if self._model:
            return self._model
        if not self._settings.openai_api_key:
            raise ProviderConfigurationError("WALT_OPENAI_API_KEY is required")
        provider = OpenAIProvider(
            api_key=self._settings.openai_api_key.get_secret_value()
        )
        self._provider = provider
        self._model = OpenAIRealtimeModel(
            self._settings.openai_realtime_model, provider=provider
        )
        return self._model

    async def _run_sideband(self, session_id: str, call: VoiceCall) -> None:
        """Attach and run PydanticAI's automatic Realtime tool loop."""
        try:
            async with call.realtime.session(
                provider_session=call.provider_session,
                retain_images_max=12,
            ) as session:
                call.attached.set()
                async for _event in session:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as error:
            call.attach_error = error
            call.attached.set()
            logger.exception(
                "realtime_sideband_failed",
                extra={
                    "demo_session_id": session_id,
                    "realtime_call_id": call.provider_session.call_id,
                },
            )
        finally:
            async with self._calls_lock:
                if self._calls.get(session_id) is call:
                    self._calls.pop(session_id, None)


def normalize_sdp(sdp: str) -> str:
    """Return canonical SDP accepted by browser WebRTC parsers.

    Args:
        sdp: Provider-generated session description.

    Returns:
        CRLF-delimited SDP without blank or padded lines.

    Raises:
        RuntimeError: The provider response is not an SDP answer.
    """
    lines = [
        line.strip()
        for line in sdp.lstrip("\ufeff")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
        if line.strip()
    ]
    if not lines or lines[0] != "v=0":
        raise RuntimeError("OpenAI returned an invalid SDP answer")
    return "\r\n".join(lines) + "\r\n"
