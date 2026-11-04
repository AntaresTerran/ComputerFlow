import time
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import Field

from computerflow.core.config import StrictModel
from computerflow.core.contracts import Action
from computerflow.core.jobs import Job


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


class DesktopContext(StrictModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    captured_at: float = Field(default_factory=time.monotonic)
    foreground_id: str | None
    windows: tuple[Window, ...] = ()
    media_sessions: tuple[MediaSession, ...] = ()
    volume_device_id: str | None = None
    volume: int | None = None
    unavailable: tuple[str, ...] = ()


class ActionResult(StrictModel):
    verified: bool
    message: str


class DesktopPlatform(Protocol):
    async def snapshot(self) -> DesktopContext: ...

    def context_is_current(self, context: DesktopContext) -> bool: ...

    async def execute(self, action: Action, context: DesktopContext, job: Job) -> ActionResult:
        """Recheck identity/focus, execute once, then inspect actual state."""
        ...
