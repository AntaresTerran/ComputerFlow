import secrets
import time
from dataclasses import dataclass

from computerflow.core.config import ExecutionConfig
from computerflow.core.contracts import ACTION_ADAPTER, Action, FocusWindow, MediaControl, SetVolume
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
        if self.config.practice_mode:
            if (
                pending is None
                or confirmation != pending
                or pending.job_id != job.id
                or pending.action_json != action.model_dump_json()
                or time.monotonic() >= pending.expires_at
            ):
                raise ComputerFlowError("Diese konkrete Aktion braucht eine neue Übungsfreigabe")
        job.state = State.EXECUTING
        result = await job.guard(self.platform.execute(action, context, job))
        job.check()
        job.state = State.DONE if result.verified else State.FAILED
        return result
