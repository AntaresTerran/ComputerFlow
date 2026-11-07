import time
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import Field

from computerflow.core.config import StrictModel
from computerflow.core.contracts import Action
from computerflow.core.jobs import Job
from computerflow.platform.geometry import Rect


class Window(StrictModel):
    id: str
    title: str
    pid: int
    application: str = ""
    process_name: str = ""
    app_aliases: tuple[str, ...] = ()


class MediaSession(StrictModel):
    id: str
    app: str
    status: Literal["playing", "paused", "other"]
    can_play: bool
    can_pause: bool
    app_aliases: tuple[str, ...] = ()


class AudioSession(StrictModel):
    id: str
    app: str
    aliases: tuple[str, ...] = ()
    level: int


class RegisteredApplication(StrictModel):
    id: str
    name: str


@dataclass(frozen=True)
class Element:
    id: str
    native_id: tuple[int, ...]
    label: str
    role: str
    rect: Rect
    operation: Literal["invoke", "toggle", "select", "write"]
    chat_input: bool = False


@dataclass(frozen=True)
class UIContext:
    id: str
    window_id: str
    captured_at: float
    elements: tuple[Element, ...] = ()
    focus: tuple[int, ...] | None = None
    protected_focus: bool = False
    complete: bool = True


@dataclass(frozen=True)
class ScreenSnapshot:
    id: str
    window_id: str
    monitor_id: str
    monitor_bounds: Rect
    crop: Rect
    image_size: tuple[int, int]
    cursor: tuple[int, int]
    captured_at: float
    png: bytes
    marks: tuple[tuple[int, Element], ...] = ()


class DesktopContext(StrictModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    captured_at: float = Field(default_factory=time.monotonic)
    foreground_id: str | None
    windows: tuple[Window, ...] = ()
    media_sessions: tuple[MediaSession, ...] = ()
    volume_device_id: str | None = None
    volume: int | None = None
    audio_sessions: tuple[AudioSession, ...] = ()
    launch_target: RegisteredApplication | None = None
    ui: UIContext | None = None
    screen: ScreenSnapshot | None = Field(default=None, exclude=True)
    unavailable: tuple[str, ...] = ()


class ActionResult(StrictModel):
    verified: bool
    message: str
    foreground_id: str | None = None


class DesktopPlatform(Protocol):
    async def snapshot(self) -> DesktopContext: ...

    def context_is_current(self, context: DesktopContext) -> bool: ...

    async def execute(self, action: Action, context: DesktopContext, job: Job) -> ActionResult:
        """Recheck identity/focus, execute once, then inspect actual state."""
        ...
