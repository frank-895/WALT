from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Reference = Annotated[
    str, Field(min_length=1, max_length=48, pattern=r"^[a-zA-Z0-9_-]+$")
]
CompanyName = Annotated[str, Field(min_length=1, max_length=120)]
VisitorName = Annotated[str, Field(min_length=1, max_length=80)]
FillValue = Annotated[str, Field(max_length=2_000)]
ScrollDelta = Annotated[int, Field(ge=-1_200, le=1_200)]
WaitMilliseconds = Annotated[int, Field(ge=50, le=3_000)]
BrowserKey = Literal[
    "Enter",
    "Escape",
    "Tab",
    "Space",
    "ArrowUp",
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "Backspace",
    "Delete",
]

DemoIndustry = Literal[
    "technology",
    "professional-services",
    "financial-services",
    "healthcare",
    "retail",
    "manufacturing",
    "other",
]
DemoTeamSize = Literal["1-10", "11-50", "51-250", "251-500", "500+"]
DemoPriority = Literal[
    "pipeline-visibility",
    "follow-up",
    "lead-organization",
    "deal-prioritization",
    "team-coordination",
    "reporting",
]
DemoPriorities = Annotated[list[DemoPriority], Field(min_length=1, max_length=3)]


class StrictModel(BaseModel):
    """Reject undeclared fields at application boundaries."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DemoBrief(StrictModel):
    """Small visitor brief used to generate a complete fictional CRM dataset."""

    company_name: CompanyName
    priorities: DemoPriorities
    industry: DemoIndustry = "other"
    team_size: DemoTeamSize = "11-50"
    visitor_name: VisitorName | None = None


class ObserveAction(StrictModel):
    """Refresh the current Atomic browser state."""

    action: Literal["observe"]


class ClickAction(StrictModel):
    """Click one control from the latest observation."""

    action: Literal["click"]
    ref: Reference
    generation: int = Field(ge=1)


class FillAction(StrictModel):
    """Replace the value of one editable control."""

    action: Literal["fill"]
    ref: Reference
    generation: int = Field(ge=1)
    value: FillValue


class HighlightAction(StrictModel):
    """Visually emphasize one target from the latest observation."""

    action: Literal["highlight"]
    ref: Reference
    generation: int = Field(ge=1)


class KeyAction(StrictModel):
    """Press one explicitly allowed keyboard key."""

    action: Literal["key"]
    key: BrowserKey


class ScrollAction(StrictModel):
    """Scroll the current Atomic page by a bounded amount."""

    action: Literal["scroll"]
    delta_y: ScrollDelta


class WaitAction(StrictModel):
    """Wait briefly before observing the page again."""

    action: Literal["wait"]
    milliseconds: WaitMilliseconds = 500


BrowserAction = Annotated[
    ObserveAction
    | ClickAction
    | FillAction
    | HighlightAction
    | KeyAction
    | ScrollAction
    | WaitAction,
    Field(discriminator="action"),
]


class BrowserControl(StrictModel):
    """Compact, short-lived description of one visible browser control."""

    ref: str
    role: str
    name: str
    disabled: bool = False
    href: str | None = None


class BrowserHighlightTarget(StrictModel):
    """Visible named content that Walt can emphasize without interacting with it."""

    ref: str
    role: str
    name: str


class BrowserActionResult(StrictModel):
    """Fresh browser state and screenshot returned after every action."""

    generation: int
    url: str
    route: str
    title: str
    controls: list[BrowserControl]
    highlight_targets: list[BrowserHighlightTarget] = Field(default_factory=list)
    state_stable: bool = True
    screenshot: str


DemoStatus = Literal["provisioning", "onboarding", "preparing", "ready", "failed"]


class DemoSessionCreated(StrictModel):
    """Opaque metadata for a newly created disposable demo."""

    id: str
    status: DemoStatus
    expires_at: datetime


class DemoSessionState(StrictModel):
    """Public status of one disposable demo session."""

    id: str
    status: DemoStatus
    expires_at: datetime
    view_url: str | None = None
    error: str | None = None


class VoiceAnswer(BaseModel):
    """WebRTC answer returned after the server sideband is attached."""

    model_config = ConfigDict(extra="forbid")

    sdp: str
    call_id: str


class DemoNotFoundError(Exception):
    """The requested demo does not exist or has expired."""


class DemoConflictError(Exception):
    """A completed demo cannot be prepared with different data."""


class DemoNotReadyError(Exception):
    """The requested demo cannot currently accept browser actions."""
