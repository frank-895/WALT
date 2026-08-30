import asyncio
import base64
import json
from dataclasses import dataclass

import pytest

from api.demo.browser import BrowserController, StaleBrowserReferenceError
from api.demo.models import ClickAction, ObserveAction


@dataclass
class ProcessResponse:
    exit_code: int | None
    result: str


@dataclass
class ScreenshotResponse:
    screenshot: str | None


class FakeBrowserSandbox:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    async def run_browser_action(self, request: str, timeout: int) -> ProcessResponse:
        self.requests.append(json.loads(base64.b64decode(request)))
        state = {
            "url": "http://127.0.0.1:8080/#/deals",
            "title": "Atomic CRM",
            "controls": [
                {"node_id": 41, "role": "button", "name": "Create deal"},
                {
                    "node_id": 42,
                    "role": "link",
                    "name": "External",
                    "href": "https://example.com",
                },
                {"node_id": 43, "role": "generic", "name": "Ignored"},
            ],
        }
        return ProcessResponse(exit_code=0, result=json.dumps(state))

    async def take_screenshot(self, quality: int, scale: float) -> ScreenshotResponse:
        return ScreenshotResponse(screenshot="jpeg-base64")


def test_controller_refreshes_refs_and_disables_external_links() -> None:
    sandbox = FakeBrowserSandbox()
    controller = BrowserController(sandbox, "http://127.0.0.1:8080", 15, 70, 0.75)

    observed = asyncio.run(controller.execute(ObserveAction(action="observe")))
    clicked = asyncio.run(
        controller.execute(ClickAction(action="click", ref="b1", generation=1))
    )

    assert observed.generation == 1
    assert [(control.ref, control.disabled) for control in observed.controls] == [
        ("b1", False),
        ("b2", True),
    ]
    assert clicked.generation == 2
    assert clicked.route == "/#/deals"
    assert sandbox.requests[1] == {"action": "click", "node_id": 41}


def test_controller_rejects_stale_refs_before_running_adapter() -> None:
    sandbox = FakeBrowserSandbox()
    controller = BrowserController(sandbox, "http://127.0.0.1:8080", 15, 70, 0.75)
    asyncio.run(controller.execute(ObserveAction(action="observe")))

    with pytest.raises(StaleBrowserReferenceError):
        asyncio.run(
            controller.execute(ClickAction(action="click", ref="b1", generation=2))
        )

    assert len(sandbox.requests) == 1
