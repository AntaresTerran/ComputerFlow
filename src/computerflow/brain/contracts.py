from typing import Protocol

from computerflow.core.contracts import Decision
from computerflow.core.jobs import Job
from computerflow.platform.contracts import DesktopContext


class InferenceBackend(Protocol):
    async def plan(
        self,
        command: str | bytes,
        context: DesktopContext,
        job: Job,
        clarification: str | None = None,
    ) -> Decision: ...
