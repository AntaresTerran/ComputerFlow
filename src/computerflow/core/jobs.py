import asyncio
import time
from collections.abc import Awaitable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, TypeVar
from uuid import uuid4

from computerflow.core.errors import Cancelled

if TYPE_CHECKING:
    from computerflow.platform.contracts import ScreenSnapshot

T = TypeVar("T")


class State(StrEnum):
    RECORDING = "Aufnahme"
    PLANNING = "Planung"
    WAITING = "Rückfrage/Freigabe"
    EXECUTING = "Ausführung"
    VERIFYING = "Prüfung"
    DONE = "Abgeschlossen"
    FAILED = "Fehler"
    CANCELLED = "Abgebrochen"


@dataclass
class Job:
    timeout_seconds: float
    id: str = field(default_factory=lambda: uuid4().hex)
    state: State = State.RECORDING
    started: float = field(default_factory=time.monotonic)
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    executed: list[str] = field(default_factory=list)
    captures: dict[str, "ScreenSnapshot"] = field(default_factory=dict)

    def cancel(self) -> None:
        self.cancelled.set()
        self.state = State.CANCELLED

    @property
    def remaining(self) -> float:
        return max(0.0, self.started + self.timeout_seconds - time.monotonic())

    def check(self) -> None:
        if self.cancelled.is_set():
            raise Cancelled("Auftrag abgebrochen; verspätete Ergebnisse werden verworfen")
        if self.remaining <= 0:
            self.cancel()
            raise Cancelled("Zeitlimit des Auftrags erreicht")

    async def guard(self, awaitable: Awaitable[T]) -> T:
        """Cancel pending I/O immediately; check again before returning any result."""
        task = asyncio.ensure_future(awaitable)
        stop = asyncio.create_task(self.cancelled.wait())
        try:
            self.check()
            done, _ = await asyncio.wait(
                {task, stop}, timeout=self.remaining, return_when=asyncio.FIRST_COMPLETED
            )
            if task not in done or stop in done:
                self.cancel()
            self.check()
            result = task.result()
            self.check()
            return result
        finally:
            task.cancel()
            stop.cancel()
            await asyncio.gather(task, stop, return_exceptions=True)
