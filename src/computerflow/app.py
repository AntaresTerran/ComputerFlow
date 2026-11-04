import asyncio
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from computerflow.actuator.executor import Confirmation, Executor
from computerflow.brain.contracts import InferenceBackend
from computerflow.core.config import Config
from computerflow.core.contracts import Act, Answer, Ask, Stop
from computerflow.core.errors import Cancelled, ComputerFlowError
from computerflow.core.jobs import Job, State
from computerflow.platform.contracts import DesktopPlatform


@dataclass(frozen=True)
class HistoryEntry:
    job_id: str
    state: State
    message: str
    executed: tuple[str, ...]
    elapsed_seconds: float


class Assistant:
    def __init__(
        self,
        config: Config,
        backend: InferenceBackend,
        platform: DesktopPlatform,
        status: Callable[[str], None] = print,
    ):
        self.config = config
        self.backend = backend
        self.platform = platform
        self.executor = Executor(platform, config.execution)
        self.status = status
        self.current: Job | None = None
        self.history: deque[HistoryEntry] = deque(maxlen=20)
        self._clarification: tuple[str, float] | None = None
        self._confirmation: Confirmation | None = None
        self._confirm_event = asyncio.Event()

    async def _watch_context(self, context, job: Job) -> None:
        while job.state in {State.PLANNING, State.WAITING}:
            if not self.platform.context_is_current(context):
                self.status("Manueller Fensterwechsel erkannt; Auftrag wird unterbrochen")
                job.cancel()
                return
            await asyncio.sleep(0.05)

    def cancel(self) -> None:
        if self.current:
            self.current.cancel()
        self.executor.clear_confirmation()
        self._confirmation = None
        self._clarification = None
        self.status("Abbruch angefordert. Bereits gesendete Systemaktionen bleiben möglich.")

    def confirm(self) -> None:
        # Only the physical console/UI path can call this, never a model response.
        if self._confirmation is not None:
            self._confirm_event.set()

    async def run(
        self,
        command: str | bytes,
        job: Job | None = None,
        on_confirmation: Callable[[str], None] | None = None,
    ) -> HistoryEntry:
        if self.current is not None:
            raise ComputerFlowError("Ein Auftrag läuft bereits")
        job = job or Job(self.config.execution.timeout_seconds)
        self.current = job
        self._confirm_event.clear()
        self._confirmation = None
        message = ""
        watcher = None
        try:
            job.check()
            job.state = State.PLANNING
            self.status(f"[{job.id[:8]}] {job.state}")
            context = await job.guard(self.platform.snapshot())
            watcher = asyncio.create_task(self._watch_context(context, job))
            for unavailable in context.unavailable:
                self.status(unavailable)
            clarification = None
            if self._clarification and time.monotonic() < self._clarification[1]:
                clarification = self._clarification[0]
            self._clarification = None
            decision = await job.guard(self.backend.plan(command, context, job, clarification))
            job.check()
            if isinstance(decision, Act):
                confirmation = None
                if self.config.execution.practice_mode:
                    confirmation = self.executor.request_confirmation(decision.action, context, job)
                    self._confirmation = confirmation
                    self.status(f"Übungsfreigabe mit F6: {decision.action.model_dump_json()}")
                    if on_confirmation:
                        action = decision.action
                        if action.type == "focus_window":
                            target = next(w for w in context.windows if w.id == action.window_id)
                            description = f"Wechsel zu {target.application or target.title}"
                        elif action.type == "media_control":
                            target = next(
                                s for s in context.media_sessions if s.id == action.session_id
                            )
                            operation = (
                                "Wiedergabe starten" if action.operation == "play" else "pausieren"
                            )
                            description = f"{target.app} {operation}"
                        else:
                            description = f"Systemlautstärke auf {action.level} Prozent setzen"
                        on_confirmation(f"{description}. Für die Übungsfreigabe drücke F6.")
                    try:
                        await job.guard(
                            asyncio.wait_for(
                                self._confirm_event.wait(),
                                timeout=self.config.execution.confirmation_timeout_seconds,
                            )
                        )
                    except TimeoutError:
                        raise ComputerFlowError("Übungsfreigabe abgelaufen") from None
                result = await self.executor.execute(decision.action, context, job, confirmation)
                message = result.message
            elif isinstance(decision, Ask):
                job.state = State.WAITING
                message = decision.question
                self._clarification = (message, time.monotonic() + 60)
            elif isinstance(decision, Answer):
                job.state = State.DONE
                message = decision.message
            elif isinstance(decision, Stop):
                job.cancel()
                self._clarification = None
                message = "Auftrag per Sprache/Text abgebrochen"
        except Cancelled as exc:
            job.state = State.CANCELLED
            message = str(exc)
        except ComputerFlowError as exc:
            job.state = State.FAILED
            message = str(exc)
        except asyncio.CancelledError:
            job.cancel()
            message = "Auftrag abgebrochen"
            raise
        except Exception:
            job.state = State.FAILED
            message = "Unerwarteter Komponentenfehler; Auftrag sicher beendet"
        finally:
            if watcher:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            entry = HistoryEntry(
                job_id=job.id,
                state=job.state,
                message=message,
                executed=tuple(job.executed),
                elapsed_seconds=round(time.monotonic() - job.started, 3),
            )
            self.history.append(entry)
            self.status(f"[{job.id[:8]}] {job.state}: {message}")
            if job.executed:
                self.status("Gesendete Schritte: " + ", ".join(job.executed))
            self.executor.clear_confirmation()
            self._confirmation = None
            self.current = None
        return entry
