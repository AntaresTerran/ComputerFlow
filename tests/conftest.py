import pytest

from computerflow.platform.contracts import ActionResult, DesktopContext, MediaSession, Window


@pytest.fixture
def context():
    return DesktopContext(
        foreground_id="10:1",
        windows=(
            Window(id="10:1", title="Editor", pid=1),
            Window(id="20:2", title="Browser", pid=2),
        ),
        volume_device_id="speakers",
        volume=40,
        media_sessions=(
            MediaSession(
                id="music",
                app="player",
                status="playing",
                can_play=True,
                can_pause=True,
            ),
        ),
    )


class SimulatedDesktop:
    """Explicitly a simulation, never used by application startup."""

    def __init__(self, context):
        self.context = context
        self.calls = []
        self.verified = True

    async def snapshot(self):
        return self.context

    def context_is_current(self, context):
        return self.context.foreground_id == context.foreground_id

    async def execute(self, action, context, job):
        job.check()
        self.calls.append(action)
        job.executed.append(action.type)
        return ActionResult(verified=self.verified, message="Simuliertes Ergebnis")


@pytest.fixture
def desktop(context):
    return SimulatedDesktop(context)
