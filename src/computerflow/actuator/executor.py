import secrets
import time
from dataclasses import dataclass

from computerflow.brain.desktop import is_browser, safe_text
from computerflow.core.config import ExecutionConfig
from computerflow.core.contracts import (
    ACTION_ADAPTER,
    Action,
    BrowserKey,
    FocusWindow,
    LaunchApplication,
    MediaControl,
    SetAppVolume,
    SetVolume,
    UIElementAction,
    VisualClick,
    WriteText,
)
from computerflow.core.errors import ComputerFlowError
from computerflow.core.jobs import Job, State
from computerflow.platform.contracts import ActionResult, DesktopContext, DesktopPlatform


@dataclass(frozen=True)
class Confirmation:
    token: str
    job_id: str
    action_json: str
    expires_at: float


class Executor:
    def __init__(self, platform: DesktopPlatform, config: ExecutionConfig):
        self.platform = platform
        self.config = config
        self._pending: Confirmation | None = None

    def needs_confirmation(self, action: Action, context: DesktopContext) -> bool:
        if self.config.practice_mode or isinstance(action, (VisualClick, LaunchApplication)):
            return True
        if isinstance(action, UIElementAction) and context.ui:
            element = next((e for e in context.ui.elements if e.id == action.element_id), None)
            # Activating an arbitrary provider button, menu item or link may commit a change.
            # Tabs are simple selection; other elements require specific confirmation.
            return (
                element is None or element.role != "Registerkarte" or element.operation != "select"
            )
        return False

    def validate(self, action: Action, context: DesktopContext, job: Job) -> None:
        job.check()
        # Revalidate at the execution boundary, including programmatically constructed models.
        ACTION_ADAPTER.validate_python(action.model_dump())
        age = time.monotonic() - context.captured_at
        if action.context_id != context.id or not 0 <= age <= self.config.context_max_age_seconds:
            raise ComputerFlowError(
                "Desktopkontext ist veraltet oder gehört zu einem anderen Auftrag"
            )
        if isinstance(action, FocusWindow):
            if not any(w.id == action.window_id for w in context.windows):
                raise ComputerFlowError("Fensterziel gehört nicht zum aktuellen Kontext")
        elif isinstance(action, LaunchApplication):
            if not context.launch_target or context.launch_target.id != action.registration_id:
                raise ComputerFlowError(
                    "Anwendung gehört nicht zur geprüften Windows-Registrierung"
                )
        elif isinstance(action, SetVolume):
            if not context.volume_device_id or action.device_id != context.volume_device_id:
                raise ComputerFlowError(
                    "Audioausgabegerät ist nicht verfügbar oder wurde verwechselt"
                )
        elif isinstance(action, MediaControl):
            matches = [s for s in context.media_sessions if s.id == action.session_id]
            if len(matches) != 1:
                raise ComputerFlowError("Wiedergabeziel ist nicht eindeutig verfügbar")
            session = matches[0]
            desired = "playing" if action.operation == "play" else "paused"
            if not getattr(session, f"can_{action.operation}") and session.status != desired:
                raise ComputerFlowError("Wiedergabeziel unterstützt diese Medienaktion nicht")
        elif isinstance(action, SetAppVolume):
            if (
                not context.volume_device_id
                or sum(s.id == action.session_id for s in context.audio_sessions) != 1
            ):
                raise ComputerFlowError("App-Wiedergabesitzung gehört nicht zum Kontext")
        elif isinstance(action, BrowserKey):
            if action.window_id != context.foreground_id or not any(
                w.id == action.window_id and is_browser(w) for w in context.windows
            ):
                raise ComputerFlowError(
                    "Browser-Tastenkombination braucht das aktive Browserfenster"
                )
        elif isinstance(action, (UIElementAction, WriteText)):
            ui = context.ui
            if (
                not ui
                or ui.id != action.ui_id
                or ui.window_id != action.window_id
                or ui.window_id != context.foreground_id
            ):
                raise ComputerFlowError("Element gehört nicht zum aktuellen Zielfenster")
            if (
                not 0
                <= time.monotonic() - ui.captured_at
                <= min(45, self.config.context_max_age_seconds)
            ):
                raise ComputerFlowError("Elementkontext ist abgelaufen")
            matches = [e for e in ui.elements if e.id == action.element_id]
            if len(matches) != 1:
                raise ComputerFlowError("Elementkennung gehört nicht zum aktuellen UI-Kontext")
            element = matches[0]
            if isinstance(action, WriteText):
                unique = ui.complete and sum(e.operation == "write" for e in ui.elements) == 1
                focus_ok = unique if action.focus_first else element.native_id == ui.focus
                if (
                    element.operation != "write"
                    or not focus_ok
                    or ui.protected_focus
                    or not safe_text(action.text)
                    or (action.in_chat and (action.focus_first or not element.chat_input))
                ):
                    raise ComputerFlowError(
                        "Text und aktiver Eingabefokus konnten nicht bestätigt werden"
                    )
            elif element.operation == "write":
                raise ComputerFlowError("Textfeld ist kein aktivierbares Element")
        elif isinstance(action, VisualClick):
            screen = context.screen
            if (
                not screen
                or screen.id != action.snapshot_id
                or screen.window_id != action.window_id
                or screen.window_id != context.foreground_id
            ):
                raise ComputerFlowError("Klick gehört nicht zur aktuellen Bildschirmaufnahme")
            if (
                not 0
                <= time.monotonic() - screen.captured_at
                <= min(45, self.config.context_max_age_seconds)
            ):
                raise ComputerFlowError("Bildschirmaufnahme ist abgelaufen")
            if action.at_cursor and not screen.crop.contains(*screen.cursor):
                raise ComputerFlowError("Mausposition liegt außerhalb der Bildschirmaufnahme")
        else:
            raise ComputerFlowError("Nicht erlaubte Aktion")

    def request_confirmation(
        self,
        action: Action,
        context: DesktopContext,
        job: Job,
    ) -> Confirmation:
        self._pending = None
        self.validate(action, context, job)
        self._pending = Confirmation(
            token=secrets.token_urlsafe(24),
            job_id=job.id,
            action_json=action.model_dump_json(),
            expires_at=time.monotonic() + self.config.confirmation_timeout_seconds,
        )
        job.state = State.WAITING
        return self._pending

    def clear_confirmation(self) -> None:
        self._pending = None

    async def execute(
        self,
        action: Action,
        context: DesktopContext,
        job: Job,
        confirmation: Confirmation | None = None,
    ) -> ActionResult:
        pending, self._pending = self._pending, None
        self.validate(action, context, job)
        if self.needs_confirmation(action, context):
            if (
                pending is None
                or confirmation != pending
                or pending.job_id != job.id
                or pending.action_json != action.model_dump_json()
                or time.monotonic() >= pending.expires_at
            ):
                raise ComputerFlowError("Diese konkrete Aktion braucht eine neue Freigabe")
        job.state = State.EXECUTING
        result = await job.guard(self.platform.execute(action, context, job))
        job.check()
        job.state = State.DONE if result.verified else State.FAILED
        return result
