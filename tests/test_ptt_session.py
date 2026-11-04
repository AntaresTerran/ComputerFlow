import asyncio

import pytest

from computerflow.app import Assistant
from computerflow.audio.session import VoiceSession
from computerflow.audio.wake import Detection
from computerflow.core.config import Config, FeedbackConfig
from computerflow.core.jobs import State


class NeverCalledBackend:
    async def plan(self, *args):
        raise AssertionError("Cancelled recording must not reach inference")


async def test_stop_between_release_and_worker_start_discards_queued_command(desktop):
    assistant = Assistant(Config(), NeverCalledBackend(), desktop, lambda _: None)
    session = VoiceSession(Config(), assistant)
    session.start()
    session.recorder._callback(b"\0\0" * 8000, 8000, None, False)
    session.finish()
    # No event-loop yield: emergency stop arrives before Assistant.run starts.
    session.cancel()
    await session.task
    assert assistant.history[-1].state == State.CANCELLED
    assert not desktop.calls
    assert not session.recorder._data


async def test_recording_limit_resets_toggle_trigger(desktop):
    assistant = Assistant(Config(), NeverCalledBackend(), desktop, lambda _: None)
    session = VoiceSession(Config(), assistant)
    session.start()
    session.trigger._active = True
    session.finish()  # too short, but trigger must still reset
    assert session.trigger._active is False
    assert session.recording is None
    session.cancel()


async def test_manual_focus_change_during_planning_cancels_command(context, desktop):
    started = asyncio.Event()

    class SlowBackend:
        async def plan(self, *args):
            started.set()
            await asyncio.sleep(30)

    assistant = Assistant(Config(), SlowBackend(), desktop, lambda _: None)
    task = asyncio.create_task(assistant.run("test"))
    await started.wait()
    desktop.context = context.model_copy(update={"foreground_id": "other"})
    entry = await asyncio.wait_for(task, 1)
    assert entry.state == State.CANCELLED
    assert not desktop.calls


@pytest.mark.parametrize("phase", ["inference", "playback"])
async def test_spoken_stop_interrupts_active_processing_or_playback(monkeypatch, phase, desktop):
    class Source:
        def reset(self):
            pass

        def feed(self, pcm, offset, purpose):
            assert purpose == "stop"
            return Detection(offset + len(pcm))

    class Voice:
        async def speak(self, message):
            entered.set()
            await asyncio.Event().wait()

        def stop(self):
            interrupted.set()

    class Backend:
        async def plan(self, *args):
            entered.set()
            await asyncio.Event().wait()

    config = Config(feedback=FeedbackConfig(mode="silent" if phase == "inference" else "brief"))
    entered, interrupted = asyncio.Event(), asyncio.Event()
    assistant = Assistant(config, Backend(), desktop, lambda _: None)
    session = VoiceSession(config, assistant, lambda _: None)
    session.source = Source()
    monkeypatch.setattr("computerflow.audio.session.VoiceActivity", lambda _: None)
    if phase == "inference":
        session.start()
        session.recorder._callback(bytes(16000), 8000, None, False)
        session.finish()
    else:
        session.feedback._voice = Voice()
        session.feedback.say("Ein längerer Satz.")
    worker = asyncio.create_task(session._listen_voice())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        session.recorder._callback(bytes(1600), 800, None, False)
        if phase == "inference":
            await asyncio.wait_for(session.task, 1)
            assert assistant.history[-1].state == State.CANCELLED
            assert not desktop.calls
        else:
            await asyncio.wait_for(interrupted.wait(), 1)
            await session.feedback.close()
            assert not session.feedback.speaking
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
