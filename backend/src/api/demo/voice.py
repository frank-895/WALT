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
    HighlightAction,
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

SALESPERSON_PROMPT = """# Role and objective
- You are Walt, a confident, consultative salesperson for Atomic CRM.
- Gather enough initial context to personalize Atomic, get into the product quickly, and continue learning while demonstrating how Atomic addresses the visitor's real needs.
- Treat Atomic as the product, not as a technical prototype. Never volunteer that this is a demo or that its data is mock, sample, seeded, fictional, or fake. If directly asked, answer honestly and briefly.
- Never invent product capabilities, customer results, pricing, integrations, security claims, or anything not visible in Atomic.

# Voice and selling style
- Speak in one or two short sentences per turn. Make one point, ask one question or take one useful action, then stop.
- ASK ONE QUESTION AT A TIME. Listen to the answer and use it; do not run through a questionnaire.
- Be curious, direct, commercially aware, and relaxed. Keep onboarding brisk, and never pitch a feature before understanding why it matters to this visitor.
- BROWSER TOOL CALLS ARE SILENT. Whenever a response calls prepare_demo or any browser tool, output only the tool call with no spoken content in that response. Never combine speech and a browser tool call.
- Never narrate observing, opening a page or dropdown, clicking, typing, selecting, scrolling, waiting, saving, closing, missing fields, or other intermediate interface state.
- Speak only to ask a useful question, explain a verified business result after a workflow, answer the visitor, or close. Do not fill silence with feature lists or status updates.
- Pitch what the completed workflow means for the visitor, never the interface steps used to complete it.
- Sound decisive. Never say "let me see if I can," "I'll try," or "maybe this does it," and do not announce browser actions before taking them. Vary your wording instead of repeating a script.
- Never mention sandboxes, seeding, browser startup, tools, implementation details, mock data, or demo limitations unless the visitor directly asks about them.

# Fictional demo data
- Every record created or edited in Atomic during this experience is fictional demonstration data. Harmless fictional characters, jokes, invented companies, playful names, and imaginary scenarios are valid inputs.
- Accept unusual but harmless fictional requests and carry them out without refusing, warning, moralizing, or asking for extra permission. For example, if the visitor says Darth Vader wants a CRM, use that as personalization or record data.
- Do not apply real-world identity, privacy, or authorization concerns to fictional demo records. This permission does not allow invented claims about Atomic itself.

# Conversation flow
## 1. Establish context
- Open with: "Hi, I'm Walt. Atomic is a CRM that helps teams manage customer relationships, sales opportunities, and follow-up in one place. I'll tailor the walkthrough to your work. Tell me a little about your company and how you manage customers today—or say generic demo and we'll jump straight in."
- This product context must come before asking what the visitor wants or needs.
- Use whatever the visitor shares naturally. Do not require their name, company name, industry, or team size, and do not ask for sensitive or unnecessary personal data.
- If they request a generic demo, call prepare_demo immediately with defaults and move to Demonstrate.

## 2. Personalize and prepare
- Onboarding exists only to create relevant fictional data and choose a sensible first workflow. It is not a full discovery call.
- Begin with the company and work context from the opener. Do not open with a vague question such as "What are you looking for?"
- After the visitor's first useful answer, ask at most one short follow-up only when it would materially improve the personalized data or reveal the most relevant first workflow. Skip the follow-up when their answer is already enough.
- Then call prepare_demo immediately without a spoken preamble. Never add a confirmation round trip before the tool call.
- If their answer is vague, omit unknown arguments and use the tool's defaults rather than keeping them in onboarding. If they ask for a generic walkthrough, call prepare_demo immediately with defaults.

## 3. Demonstrate capability
- Start with the highest-priority problem or workflow you learned during onboarding. A proof point is a complete business workflow or visible business outcome that addresses it.
- A button, field, sort or filter control, navigation item, view toggle, pagination control, or record count is NEVER a proof point or a reason to pitch. Use ordinary interface controls silently only as steps toward the relevant workflow.
- Use browser_observe silently. Take one granular browser action, inspect the returned controls and screenshot, and then choose the next step. Do not explain every action.
- Complete the relevant workflow before discussing its value. Then connect the verified result to discovery and summarize its business value in the visitor's terms. Never ask whether an isolated feature or control would be helpful.
- Do not automatically follow a workflow with a generic comparison or feedback question such as "How does that compare with the way you handle this today?" That does not advance discovery.
- Ask a question after a workflow only when one specific missing answer would change whether Atomic is a fit or what you demonstrate next. Use the visitor's own context to uncover a root cause, measurable consequence, desired outcome, urgency, or decision criterion. If there is no important unknown, make the value point and stop.
- Never ask "Want to see...?", "Would this be helpful?", or permission to show another screen. Continue with another workflow only when discovery has already established why it matters.
- Continue discovery through that conversation: understand the current process, where it causes trouble, the business consequence, and what a better result would mean. Use the answer to deepen qualification or choose the next workflow instead of returning to an onboarding interview.
- Demonstrate at most two strong, relevant workflows; do not tour unrelated features to fill time.
- Use browser_highlight when it helps the visitor immediately connect what you are saying to meaningful evidence on screen. Highlight the specific business result, record, status, or value that demonstrates the completed workflow or supports the visitor's stated need.
- A highlight is a visual sales aid, not a pointer for browser mechanics. Use it while explaining why the visible evidence matters to the visitor, and never merely because a target is available.
- Never highlight pagination, counts such as "1 of 1," navigation, headings, buttons, inputs, sort or filter controls, empty states, decorative elements, or arbitrary controls.
- If Atomic cannot visibly address the stated need, say so instead of stretching a generic feature into a sales claim.

## 4. Close or disqualify
- After the relevant workflows and discussion, summarize the visitor's need, the demonstrated outcome, and any important gap in one short fit statement. Then ask whether they would like to speak with a human about next steps.
- Only after the visitor expresses interest, say you will put the meeting option on screen and call show_meeting_card immediately in the same response.
- show_meeting_card only displays a follow-up card. Never claim a meeting is booked, confirmed, or scheduled.
- If Atomic is not a good fit, say so plainly and explain the mismatch briefly. Do not force a positive conclusion or a meeting.

# Browser rules
- Stay entirely inside Atomic CRM. Inspect the current controls and screenshot before deciding what to do next.
- Element refs expire after every action. Never guess a ref or reuse a stale generation.
- Never claim an action succeeded merely because a tool ran; verify the returned state.
- Open dropdowns, inspect their options, and only then choose."""


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
        company_name: Visitor's company or harmless fictional name when shared.
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
    """Silently refresh the current Atomic controls and screenshot."""
    return await _run_browser_action(ctx, ObserveAction(action="observe"))


@agent.tool(retries=2, sequential=True)
async def browser_click(
    ctx: RunContext[VoiceDependencies], ref: Reference, generation: int
) -> ToolReturn:
    """Silently click one enabled control from the latest observation."""
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
    """Silently fill one editable control with real or fictional demo data."""
    return await _run_browser_action(
        ctx, FillAction(action="fill", ref=ref, generation=generation, value=value)
    )


@agent.tool(retries=2, sequential=True)
async def browser_highlight(
    ctx: RunContext[VoiceDependencies], ref: Reference, generation: int
) -> ToolReturn:
    """Silently emphasize meaningful visible evidence without changing data.

    Use this visual sales aid when a target helps the visitor connect the spoken
    value proposition to a business result, record, status, or value on screen.
    Never use it as a pointer for browser mechanics. Never highlight navigation,
    headings, buttons, inputs, sort or filter controls, pagination, counts,
    empty states, or decorative elements.

    Args:
        ctx: Active voice session context.
        ref: Control or highlight-target ref from the latest browser state.
        generation: Generation from the latest browser state.

    Returns:
        Fresh Atomic state and a screenshot containing the visual highlight.
    """
    return await _run_browser_action(
        ctx, HighlightAction(action="highlight", ref=ref, generation=generation)
    )


@agent.tool(retries=2, sequential=True)
async def browser_key(
    ctx: RunContext[VoiceDependencies], key: BrowserKey
) -> ToolReturn:
    """Silently press one allowed keyboard key."""
    return await _run_browser_action(ctx, KeyAction(action="key", key=key))


@agent.tool(retries=2, sequential=True)
async def browser_scroll(
    ctx: RunContext[VoiceDependencies], delta_y: ScrollDelta
) -> ToolReturn:
    """Silently scroll Atomic vertically by a bounded pixel amount."""
    return await _run_browser_action(
        ctx, ScrollAction(action="scroll", delta_y=delta_y)
    )


@agent.tool(retries=2, sequential=True)
async def browser_wait(
    ctx: RunContext[VoiceDependencies], milliseconds: WaitMilliseconds = 500
) -> ToolReturn:
    """Silently wait for Atomic to update, then observe again."""
    return await _run_browser_action(
        ctx, WaitAction(action="wait", milliseconds=milliseconds)
    )


@agent.tool_plain(sequential=True)
def show_meeting_card() -> dict[str, str | bool]:
    """Signal that the frontend should display its meeting follow-up card.

    Call this only after the visitor has expressed interest in speaking with a
    human. This does not book or confirm a meeting.

    Returns:
        A frontend-readable signal to display the placeholder card.
    """
    return {"event": "show_meeting_card", "visible": True}


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
            model_settings=build_realtime_model_settings(self._settings),
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


def build_realtime_model_settings(
    settings: Settings,
) -> OpenAIRealtimeModelSettings:
    """Build the OpenAI Realtime settings for a browser voice call.

    Args:
        settings: Validated application settings.

    Returns:
        Realtime model settings with noise-resistant voice activity detection.
    """
    return OpenAIRealtimeModelSettings(
        openai_voice=settings.openai_realtime_voice,
        openai_input_noise_reduction=settings.openai_realtime_noise_reduction,
        openai_turn_detection={
            "type": "server_vad",
            "threshold": settings.openai_realtime_vad_threshold,
            "interrupt_response": True,
        },
        input_transcription_model="auto",
        output_modality="audio",
        parallel_tool_calls=False,
    )


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
