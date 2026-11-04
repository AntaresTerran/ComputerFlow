"""Exercise real offline models and the production audio path with synthetic speech."""

import asyncio
import math
import time
import wave
from array import array
from pathlib import Path

from computerflow.app import Assistant
from computerflow.audio.session import VoiceSession
from computerflow.audio.wake import VoskSource
from computerflow.brain.llama_cpp import LlamaCppBackend
from computerflow.core.config import FeedbackConfig, load_config
from computerflow.core.contracts import Act, Answer
from computerflow.core.jobs import State
from computerflow.platform.contracts import DesktopContext, Window
from computerflow.runtime.manager import ManagedRuntime

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / ".computerflow/validation"
BLOCK = 1600


def pcm(name):
    with wave.open(str(AUDIO / f"{name}.wav")) as file:
        assert (file.getframerate(), file.getnchannels(), file.getsampwidth()) == (16000, 1, 2)
        return file.readframes(file.getnframes())


def melody(count):
    notes = (196, 220, 261.63, 329.63, 293.66, 246.94)
    for i in range(count):
        pitch = notes[(i // 4000) % len(notes)]
        time_in_note = (i % 4000) / 16000
        wave_sample = math.sin(math.tau * pitch * time_in_note)
        yield round(300 * wave_sample * math.sin(math.pi * (i % 4000) / 4000))


def mix(foreground, background):
    signal = array("h", foreground)
    mixed = array(
        "h",
        (max(-32768, min(32767, a + b)) for a, b in zip(signal, background, strict=True)),
    )
    return mixed.tobytes()


def first_detection(source, sound, purpose):
    source.reset()
    for offset in range(0, len(sound), BLOCK):
        block = sound[offset : offset + BLOCK]
        if source.feed(block, offset, purpose):
            return round((offset + len(block)) / 32000, 2)
    return None


class ReadOnlyContext:
    async def snapshot(self):
        return DesktopContext(
            foreground_id="window-a",
            windows=(Window(id="window-a", title="Notizen.txt", pid=1, application="Editor"),),
            volume=40,
            volume_device_id="validation-only",
        )

    def context_is_current(self, context):
        return True


class PlanProbe:
    def __init__(self, backend):
        self.backend = backend
        self.decision = None

    async def plan(self, command, context, job, clarification):
        self.decision = await self.backend.plan(command, context, job, clarification)
        return Answer(kind="answer", message="Sprachtest ausgewertet")


async def stream(session, audio):
    for offset in range(0, len(audio), BLOCK):
        block = audio[offset : offset + BLOCK]
        session.recorder._callback(block, len(block) // 2, None, False)
        await asyncio.sleep(len(block) / 32000)


async def run():
    config = load_config(ROOT / "config.yaml").model_copy(
        update={"feedback": FeedbackConfig(mode="silent")}
    )
    recognizer = VoskSource(config)
    for name, mode in (
        ("wake_only", "wake"),
        ("wake_joined", "wake"),
        ("stop_short", "stop"),
        ("stop_wake", "stop"),
        ("stop", "stop"),
    ):
        detected = await asyncio.to_thread(
            first_detection, recognizer, pcm(name) + bytes(32000), mode
        )
        assert detected is not None, (name, mode)
        print(f"{name}: {detected:.2f} s", flush=True)
    for name in ("negative", "negative_stop", "spotify_pause"):
        for mode in ("wake", "stop"):
            detected = await asyncio.to_thread(
                first_detection, recognizer, pcm(name) + bytes(32000), mode
            )
            assert detected is None, (name, mode, detected)

    managed = ManagedRuntime(config)
    server = managed.connection()
    assert server is not None
    backend = LlamaCppBackend(config.model, api_key=server["api_key"], on_transcript=print)
    try:
        volume_with_tail = pcm("wake_volume") + bytes(64000)
        speech_stream = array("h", pcm("negative_stop"))
        joined_with_tail = pcm("wake_joined") + bytes(64000)
        for name, sound, expected in (
            ("joined", pcm("wake_joined"), "focus_window"),
            (
                "music",
                mix(volume_with_tail, melody(len(volume_with_tail) // 2)),
                "set_volume",
            ),
            (
                "stream speech",
                mix(
                    joined_with_tail,
                    (
                        round(0.09 * speech_stream[i % len(speech_stream)])
                        for i in range(len(joined_with_tail) // 2)
                    ),
                ),
                "focus_window",
            ),
            ("bare wake", pcm("wake_only"), None),
        ):
            probe = PlanProbe(backend)
            assistant = Assistant(config, probe, ReadOnlyContext(), print)
            session = VoiceSession(config, assistant, print)
            session.source = recognizer
            recognizer.reset()
            worker = asyncio.create_task(session._listen_voice())
            try:
                started = time.monotonic()
                await stream(session, sound + bytes(64000))
                if expected:
                    assert session.task is not None, name
                    await asyncio.wait_for(session.task, 15)
                    assert isinstance(probe.decision, Act), probe.decision
                    assert probe.decision.action.type == expected, probe.decision
                    if expected == "set_volume":
                        assert probe.decision.action.level == 50, probe.decision
                    assert assistant.history[-1].state == State.DONE
                else:
                    assert session.task is None and not assistant.history
                print(f"{name}: passed in {time.monotonic() - started:.2f} s", flush=True)
            finally:
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
                session.cancel()
    finally:
        await backend.close()


if __name__ == "__main__":
    asyncio.run(run())
