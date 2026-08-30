import asyncio
from unittest.mock import AsyncMock, patch

from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.realtime import WebRTCSession

from api.demo.models import VoiceAnswer
from api.demo.voice import (
    SALESPERSON_PROMPT,
    PydanticVoiceRuntime,
    VoiceCall,
    agent,
    build_realtime_model_settings,
    normalize_sdp,
    show_meeting_card,
)
from api.settings import Settings


def test_voice_agent_exposes_only_nine_small_sequential_tools() -> None:
    tools = agent._function_toolset.tools

    assert list(tools) == [
        "prepare_demo",
        "browser_observe",
        "browser_click",
        "browser_fill",
        "browser_highlight",
        "browser_key",
        "browser_scroll",
        "browser_wait",
        "show_meeting_card",
    ]
    assert all(tool.sequential for tool in tools.values())
    assert tools["prepare_demo"].max_retries == 2
    prepare_schema = tools["prepare_demo"].function_schema.json_schema
    priority_schema = prepare_schema["properties"]["priorities"]["anyOf"][0]
    assert priority_schema["minItems"] == 1
    assert priority_schema["maxItems"] == 3
    assert "company_name" not in prepare_schema.get("required", [])
    assert "priorities" not in prepare_schema.get("required", [])
    assert prepare_schema["properties"]["team_size"]["enum"] == [
        "1-10",
        "11-50",
        "51-250",
        "251-500",
        "500+",
    ]
    highlight_schema = tools["browser_highlight"].function_schema.json_schema
    assert highlight_schema["required"] == ["ref", "generation"]
    highlight_description = tools["browser_highlight"].description
    assert highlight_description is not None
    assert "Default to not using this tool" in highlight_description
    assert "sort or filter controls" in highlight_description
    for tool_name in [
        "browser_observe",
        "browser_click",
        "browser_fill",
        "browser_highlight",
        "browser_key",
        "browser_scroll",
        "browser_wait",
    ]:
        description = tools[tool_name].description
        assert description is not None
        assert "silently" in description.lower()
    meeting_schema = tools["show_meeting_card"].function_schema.json_schema
    assert meeting_schema["properties"] == {}


def test_sales_prompt_runs_a_concise_consultative_sales_conversation() -> None:
    assert "confident, consultative salesperson" in SALESPERSON_PROMPT
    assert "Speak in one or two short sentences per turn" in SALESPERSON_PROMPT
    assert "ASK ONE QUESTION AT A TIME" in SALESPERSON_PROMPT
    assert "never pitch a feature before understanding why it matters" in (
        SALESPERSON_PROMPT
    )
    assert "Continue discovery through that conversation" in SALESPERSON_PROMPT
    assert "the business consequence" in SALESPERSON_PROMPT
    assert "If Atomic is not a good fit, say so plainly" in SALESPERSON_PROMPT


def test_sales_prompt_keeps_browser_mechanics_silent() -> None:
    assert "Browser mechanics are silent by default" in SALESPERSON_PROMPT
    assert "Never narrate observing" in SALESPERSON_PROMPT
    assert "Speak only to ask a useful question" in SALESPERSON_PROMPT
    assert "never the interface steps" in SALESPERSON_PROMPT


def test_sales_prompt_accepts_harmless_fictional_demo_data() -> None:
    assert "Every record created or edited in Atomic" in SALESPERSON_PROMPT
    assert "Harmless fictional characters, jokes" in SALESPERSON_PROMPT
    assert "Darth Vader wants a CRM" in SALESPERSON_PROMPT
    assert "without refusing, warning, moralizing" in SALESPERSON_PROMPT


def test_sales_prompt_establishes_product_context_before_discovery() -> None:
    product_context = "Atomic is a CRM that helps teams manage customer relationships"
    discovery_question = "Tell me a little about your company"

    assert product_context in SALESPERSON_PROMPT
    assert SALESPERSON_PROMPT.index(product_context) < SALESPERSON_PROMPT.index(
        discovery_question
    )
    assert "This product context must come before asking" in SALESPERSON_PROMPT
    assert 'Do not open with a vague question such as "What are you looking for?"' in (
        SALESPERSON_PROMPT
    )


def test_sales_prompt_keeps_onboarding_to_one_optional_follow_up() -> None:
    assert "Onboarding exists only to create relevant fictional data" in (
        SALESPERSON_PROMPT
    )
    assert "ask at most one short follow-up" in SALESPERSON_PROMPT
    assert "call prepare_demo immediately in the same response" in SALESPERSON_PROMPT
    assert "Never add a confirmation round trip" in SALESPERSON_PROMPT
    assert "use the tool's defaults rather than keeping them in onboarding" in (
        SALESPERSON_PROMPT
    )


def test_sales_prompt_requires_outcome_led_workflows_not_feature_pitches() -> None:
    assert "A proof point is a complete business workflow" in SALESPERSON_PROMPT
    assert "sort or filter control" in SALESPERSON_PROMPT
    assert "NEVER a proof point or a reason to pitch" in SALESPERSON_PROMPT
    assert "Complete the relevant workflow before discussing its value" in (
        SALESPERSON_PROMPT
    )
    assert "Never ask whether an isolated feature or control would be helpful" in (
        SALESPERSON_PROMPT
    )


def test_sales_prompt_defaults_to_no_highlight() -> None:
    assert "Default to no highlight" in SALESPERSON_PROMPT
    assert "at most once in the entire conversation" in SALESPERSON_PROMPT
    assert 'Never highlight pagination, counts such as "1 of 1,"' in (
        SALESPERSON_PROMPT
    )


def test_sales_prompt_only_offers_a_meeting_after_expressed_interest() -> None:
    assert "visitor expresses interest" in SALESPERSON_PROMPT
    assert "call show_meeting_card immediately" in SALESPERSON_PROMPT
    assert "only displays a follow-up card" in SALESPERSON_PROMPT
    assert "Never claim a meeting is booked" in SALESPERSON_PROMPT


def test_show_meeting_card_returns_a_frontend_signal() -> None:
    assert show_meeting_card() == {"event": "show_meeting_card", "visible": True}


def test_normalize_sdp_uses_browser_safe_line_endings() -> None:
    normalized = normalize_sdp("v=0\no=- 1 1 IN IP4 127.0.0.1\n a=ice-pwd:valid \n")

    assert normalized == ("v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\na=ice-pwd:valid\r\n")
    assert VoiceAnswer(sdp=normalized, call_id="call-1").sdp.endswith("\r\n")


def test_realtime_model_settings_reduce_false_interruptions() -> None:
    model_settings = build_realtime_model_settings(
        Settings(
            openai_realtime_vad_threshold=0.85,
            openai_realtime_noise_reduction="far_field",
        )
    )

    assert model_settings["openai_input_noise_reduction"] == "far_field"
    assert model_settings["openai_turn_detection"] == {
        "type": "server_vad",
        "threshold": 0.85,
        "interrupt_response": True,
    }


def test_close_session_hangs_up_openai_call() -> None:
    async def exercise() -> None:
        async def wait_forever() -> None:
            await asyncio.Event().wait()

        runtime = PydanticVoiceRuntime(Settings())
        provider = OpenAIProvider(api_key="test-key")
        runtime._provider = provider
        task = asyncio.create_task(wait_forever())
        runtime._calls["demo-1"] = VoiceCall(
            realtime=None,
            provider_session=WebRTCSession("openai", session_id="call-1"),
            task=task,
        )

        with patch.object(
            provider.client.realtime.calls,
            "hangup",
            new_callable=AsyncMock,
        ) as hangup:
            await runtime.close_session("demo-1")

        hangup.assert_awaited_once_with("call-1")
        assert task.cancelled()

    asyncio.run(exercise())
