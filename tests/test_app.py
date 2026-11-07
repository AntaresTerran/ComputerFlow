import asyncio

from computerflow.app import Assistant
from computerflow.core.config import Config, ExecutionConfig
from computerflow.core.contracts import Act, Ask, SetVolume
from computerflow.core.jobs import State


class ScriptedBackend:
    def __init__(self, decisions):
        self.decisions = iter(decisions)
        self.questions = []

    async def plan(self, command, context, job, clarification=None):
        self.questions.append(clarification)
        return next(self.decisions)


async def test_clarification_does_not_execute_and_is_passed_to_followup(context, desktop):
    model = ScriptedBackend(
        [
            Ask(kind="ask", question="Welche Lautstärke?"),
            Act(
                kind="act",
                action=SetVolume(
                    type="set_volume",
                    context_id=context.id,
                    device_id="speakers",
                    level=20,
                ),
            ),
        ]
    )
    assistant = Assistant(Config(), model, desktop, lambda _: None)
    first = await assistant.run("Lautstärke ändern")
    assert first.state == State.WAITING
    assert not desktop.calls
    second = await assistant.run("20 Prozent")
    assert second.state == State.DONE
    assert model.questions == [None, Ask(kind="ask", question="Welche Lautstärke?")]


async def test_practice_requires_explicit_f6_path(context, desktop):
    action = SetVolume(type="set_volume", context_id=context.id, device_id="speakers", level=20)
    model = ScriptedBackend([Act(kind="act", action=action)])
    config = Config(execution=ExecutionConfig(practice_mode=True))
    waiting = asyncio.Event()
    assistant = Assistant(
        config,
        model,
        desktop,
        lambda message: waiting.set() if "Übungsfreigabe" in message else None,
    )
    task = asyncio.create_task(assistant.run("20 Prozent"))
    await waiting.wait()
    assert not desktop.calls
    assistant.confirm()
    assert (await task).state == State.DONE
    assert len(desktop.calls) == 1


async def test_cancel_while_awaiting_confirmation_cannot_be_revived(context, desktop):
    action = SetVolume(type="set_volume", context_id=context.id, device_id="speakers", level=20)
    model = ScriptedBackend([Act(kind="act", action=action)])
    waiting = asyncio.Event()
    assistant = Assistant(
        Config(execution=ExecutionConfig(practice_mode=True)),
        model,
        desktop,
        lambda message: waiting.set() if "Übungsfreigabe" in message else None,
    )
    task = asyncio.create_task(assistant.run("20 Prozent"))
    await waiting.wait()
    assistant.cancel()
    assistant.confirm()
    assert (await task).state == State.CANCELLED
    assert not desktop.calls
