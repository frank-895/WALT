import base64
import json
from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

from api.demo.browser import BrowserController
from api.demo.models import DemoBrief, VoiceAnswer
from api.main import create_app
from api.settings import Settings


@dataclass
class ProcessResponse:
    exit_code: int | None = 0
    result: str = ""


@dataclass
class ScreenshotResponse:
    screenshot: str | None = base64.b64encode(b"jpeg").decode()


class FakeBrowserSandbox:
    async def run_browser_action(self, request: str, timeout: int) -> ProcessResponse:
        action = json.loads(base64.b64decode(request))
        return ProcessResponse(
            result=json.dumps(
                {
                    "url": "http://127.0.0.1:8080/deals",
                    "title": "Atomic CRM",
                    "controls": [{"node_id": 7, "role": "button", "name": "New deal"}],
                    "last_action": action,
                }
            )
        )

    async def take_screenshot(self, quality: int, scale: float) -> ScreenshotResponse:
        return ScreenshotResponse()


class FakeSandboxProvider:
    def __init__(self) -> None:
        self.seed: dict[str, Any] | None = None
        self.deleted = 0
        self.browser = FakeBrowserSandbox()

    async def create(self, session_id: str) -> object:
        return object()

    async def start_desktop(self, sandbox: object) -> None:
        return None

    async def create_view_url(self, sandbox: object, expires_in_seconds: int) -> str:
        return "https://preview.example.test/no-vnc"

    async def upload_seed(self, sandbox: object, seed: dict[str, Any]) -> None:
        self.seed = seed

    async def start_demo(self, sandbox: object) -> None:
        return None

    def browser_controller(self, sandbox: object) -> BrowserController:
        return BrowserController(
            self.browser,
            "http://127.0.0.1:8080",
            15,
            70,
            0.75,
        )

    async def delete(self, sandbox: object) -> None:
        self.deleted += 1

    async def close(self) -> None:
        return None


class FakeVoiceRuntime:
    def __init__(self) -> None:
        self.offers: list[str] = []
        self.closed_sessions: list[str] = []

    async def answer_offer(
        self, session_id: str, sdp_offer: str, demo_tools: Any
    ) -> VoiceAnswer:
        self.offers.append(sdp_offer)
        await demo_tools.prepare(
            session_id,
            DemoBrief(
                company_name="Acme",
                industry="technology",
                team_size="11-50",
                priorities=["pipeline-visibility"],
            ),
        )
        return VoiceAnswer(sdp="answer-sdp", call_id="call-1")

    async def close_session(self, session_id: str) -> None:
        self.closed_sessions.append(session_id)

    async def close(self) -> None:
        return None


def test_voice_demo_session_lifecycle() -> None:
    sandboxes = FakeSandboxProvider()
    voice = FakeVoiceRuntime()
    app = create_app(
        Settings(environment="test"),
        sandbox_provider=sandboxes,
        voice_runtime=voice,
    )

    with TestClient(app) as client:
        created = client.post("/api/demo-sessions")
        assert created.status_code == 201
        session_id = created.json()["id"]
        assert created.json()["status"] == "provisioning"
        assert "realtime_client_secret" not in created.json()

        offered = client.post(
            f"/api/demo-sessions/{session_id}/offer",
            content="v=0",
            headers={"Content-Type": "application/sdp"},
        )
        assert offered.status_code == 200
        assert offered.json() == {"sdp": "answer-sdp", "call_id": "call-1"}

        status = client.get(f"/api/demo-sessions/{session_id}")
        assert status.json()["status"] == "ready"
        assert status.json()["view_url"] == "https://preview.example.test/no-vnc"
        assert (
            client.post(f"/api/demo-sessions/{session_id}/prepare").status_code == 404
        )
        assert (
            client.post(f"/api/demo-sessions/{session_id}/browser-actions").status_code
            == 404
        )

        assert client.delete(f"/api/demo-sessions/{session_id}").status_code == 204
        assert client.delete(f"/api/demo-sessions/{session_id}").status_code == 204

    assert voice.offers == ["v=0"]
    assert voice.closed_sessions == [session_id]
    assert sandboxes.seed is not None
    assert sandboxes.seed["companies"][0]["name"] == "Acme"
    assert sandboxes.deleted == 1


def test_offer_rejects_empty_sdp_and_unknown_session() -> None:
    app = create_app(
        Settings(environment="test"),
        sandbox_provider=FakeSandboxProvider(),
        voice_runtime=FakeVoiceRuntime(),
    )

    with TestClient(app) as client:
        session_id = client.post("/api/demo-sessions").json()["id"]
        assert (
            client.post(
                f"/api/demo-sessions/{session_id}/offer", content=""
            ).status_code
            == 400
        )
        assert (
            client.post("/api/demo-sessions/missing/offer", content="v=0").status_code
            == 404
        )
