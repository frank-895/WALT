import asyncio
import base64
import json
from typing import Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from api.demo.models import (
    BrowserAction,
    BrowserActionResult,
    BrowserControl,
    ClickAction,
    FillAction,
)

INTERACTIVE_ROLES = {
    "button",
    "checkbox",
    "combobox",
    "link",
    "listbox",
    "menuitem",
    "option",
    "radio",
    "searchbox",
    "slider",
    "spinbutton",
    "switch",
    "tab",
    "textbox",
}


class BrowserActionError(Exception):
    """Base error for a rejected or failed browser operation."""


class StaleBrowserReferenceError(BrowserActionError):
    """The requested element reference no longer describes the page."""


class BrowserUnavailableError(BrowserActionError):
    """The sandbox browser is unavailable or returned invalid state."""


class ProcessResult(Protocol):
    """Minimal Daytona process result consumed by the controller."""

    @property
    def exit_code(self) -> int | None:
        """Return the command exit code."""
        ...

    @property
    def result(self) -> str:
        """Return standard output."""
        ...


class ScreenshotResult(Protocol):
    """Minimal Daytona screenshot result consumed by the controller."""

    @property
    def screenshot(self) -> str | None:
        """Return the base64 screenshot payload."""
        ...


class BrowserSandbox(Protocol):
    """Minimal sandbox operations required by BrowserController."""

    async def run_browser_action(
        self, command: str, request: str, timeout: int
    ) -> ProcessResult:
        """Run the fixed image-owned browser adapter."""
        ...

    async def take_screenshot(self, quality: int, scale: float) -> ScreenshotResult:
        """Capture a compressed desktop screenshot."""
        ...


class RawControl(BaseModel):
    """One accessibility control returned by the image-owned adapter."""

    model_config = ConfigDict(extra="ignore")

    node_id: int
    role: str
    name: str = ""
    visible: bool = True
    disabled: bool = False
    href: str | None = None


class RawBrowserState(BaseModel):
    """Browser state returned by the fixed JSON adapter."""

    model_config = ConfigDict(extra="ignore")

    url: str
    title: str = ""
    controls: list[RawControl] = Field(default_factory=list)


class BrowserController:
    """Serialize six safe Browser Use operations against one Chromium session."""

    def __init__(
        self,
        sandbox: BrowserSandbox,
        command: str,
        atomic_origin: str,
        timeout_seconds: int,
        screenshot_quality: int,
        screenshot_scale: float,
    ) -> None:
        """Create a controller for one sandbox.

        Args:
            sandbox: Safe process and screenshot facade for the sandbox.
            command: Fixed image-owned runner executable.
            atomic_origin: Only origin browser state may use.
            timeout_seconds: Per-operation runner timeout.
            screenshot_quality: JPEG quality for Realtime vision.
            screenshot_scale: Screenshot scale for Realtime vision.
        """
        self._sandbox = sandbox
        self._command = command
        self._atomic_origin = atomic_origin.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._screenshot_quality = screenshot_quality
        self._screenshot_scale = screenshot_scale
        self._lock = asyncio.Lock()
        self._generation = 0
        self._nodes: dict[str, int] = {}

    async def execute(self, action: BrowserAction) -> BrowserActionResult:
        """Execute one allowed action and return a fully refreshed observation.

        Args:
            action: Validated browser action.

        Returns:
            Fresh accessibility state and desktop screenshot.

        Raises:
            StaleBrowserReferenceError: A ref came from an older page generation.
            BrowserUnavailableError: The fixed adapter or screenshot service failed.
        """
        async with self._lock:
            request = action.model_dump()
            if isinstance(action, ClickAction | FillAction):
                if (
                    action.generation != self._generation
                    or action.ref not in self._nodes
                ):
                    raise StaleBrowserReferenceError(
                        "Refresh browser controls and try again"
                    )
                request["node_id"] = self._nodes[action.ref]
                request.pop("ref")
                request.pop("generation")
            encoded_request = base64.b64encode(
                json.dumps(request, separators=(",", ":")).encode()
            ).decode()
            process_result = await self._sandbox.run_browser_action(
                self._command, encoded_request, self._timeout_seconds
            )
            if process_result.exit_code != 0:
                raise BrowserUnavailableError(
                    "The browser action could not be completed"
                )
            try:
                state = RawBrowserState.model_validate_json(process_result.result)
            except ValueError as error:
                raise BrowserUnavailableError(
                    "The browser adapter returned invalid state"
                ) from error
            self._enforce_atomic_origin(state.url)
            self._generation += 1
            controls, nodes = self._compact_controls(state.controls)
            self._nodes = nodes
            screenshot_result = await self._sandbox.take_screenshot(
                self._screenshot_quality, self._screenshot_scale
            )
            if not screenshot_result.screenshot:
                raise BrowserUnavailableError("The desktop screenshot was empty")
            route = urlsplit(state.url).path or "/"
            return BrowserActionResult(
                generation=self._generation,
                url=state.url,
                route=route,
                title=state.title,
                controls=controls,
                screenshot=screenshot_result.screenshot,
            )

    def _compact_controls(
        self, controls: list[RawControl]
    ) -> tuple[list[BrowserControl], dict[str, int]]:
        """Filter the AX tree and assign short-lived references.

        Args:
            controls: Raw accessibility controls from Browser Use.

        Returns:
            Compact public controls and their private node mapping.
        """
        compact: list[BrowserControl] = []
        nodes: dict[str, int] = {}
        for control in controls:
            if (
                not control.visible
                or control.role not in INTERACTIVE_ROLES
                or not control.name.strip()
            ):
                continue
            ref = f"b{len(compact) + 1}"
            external_href = (
                control.href
                if control.href and not self._is_atomic_url(control.href)
                else None
            )
            compact.append(
                BrowserControl(
                    ref=ref,
                    role=control.role,
                    name=control.name[:240],
                    disabled=control.disabled or external_href is not None,
                    href=control.href,
                )
            )
            if external_href is None and not control.disabled:
                nodes[ref] = control.node_id
        return compact, nodes

    def _enforce_atomic_origin(self, url: str) -> None:
        """Fail closed if Chromium has left Atomic.

        Args:
            url: Current page URL.

        Raises:
            BrowserUnavailableError: The URL is not within Atomic.
        """
        if not self._is_atomic_url(url):
            raise BrowserUnavailableError("Chromium left the Atomic application")

    def _is_atomic_url(self, url: str) -> bool:
        """Return whether a URL shares Atomic's origin.

        Args:
            url: Absolute or root-relative URL.

        Returns:
            Whether the URL is safe for the demo browser.
        """
        if url.startswith("/"):
            return True
        expected = urlsplit(self._atomic_origin)
        actual = urlsplit(url)
        return actual.scheme == expected.scheme and actual.netloc == expected.netloc
