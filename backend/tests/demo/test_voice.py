import asyncio
from unittest.mock import AsyncMock, patch

from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.realtime import WebRTCSession

from api.demo.models import VoiceAnswer
from api.demo.voice import PydanticVoiceRuntime, VoiceCall, agent, normalize_sdp
from api.settings import Settings


def test_voice_agent_exposes_only_seven_small_sequential_tools() -> None:
    tools = agent._function_toolset.tools

    assert list(tools) == [
        "prepare_demo",
        "browser_observe",
        "browser_click",
        "browser_fill",
        "browser_key",
        "browser_scroll",
        "browser_wait",
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


def test_normalize_sdp_uses_browser_safe_line_endings() -> None:
    normalized = normalize_sdp("v=0\no=- 1 1 IN IP4 127.0.0.1\n a=ice-pwd:valid \n")

    assert normalized == ("v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\na=ice-pwd:valid\r\n")
    assert VoiceAnswer(sdp=normalized, call_id="call-1").sdp.endswith("\r\n")


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
