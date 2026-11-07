"""Short local feedback with a separate, interruptible playback lifecycle."""

import asyncio
import re
import time
from collections.abc import Callable

from computerflow.audio.ducking import Ducking
from computerflow.audio.wake import STOP_WORDS
from computerflow.core.config import FeedbackConfig


class WindowsVoice:
    def __init__(self):
        from comtypes.client import CreateObject

        self.voice = CreateObject("SAPI.SpVoice", dynamic=True)
        german = self.voice.GetVoices("Language=407")
        if german.Count == 0:
            raise RuntimeError("Keine lokale deutsche Windows-Stimme")
        self.voice.Voice = german.Item(0)

    async def speak(self, text: str) -> None:
        # 1 = async, 16 = plain text. A model answer can never inject SAPI XML.
        self.voice.Speak(text, 17)
        try:
            async with asyncio.timeout(20):
                # SAPI exposes completion through COM rather than an asyncio event.
                while not self.voice.WaitUntilDone(0):  # noqa: ASYNC110
                    await asyncio.sleep(0.03)
        finally:
            self.stop()

    def stop(self) -> None:
        self.voice.Speak("", 19)  # async, purge queued audio, plain text


class Feedback:
    def __init__(self, config: FeedbackConfig, status: Callable[[str], None], ducking: Ducking):
        self.config = config
        self.status = status
        self.ducking = ducking
        self._voice = None
        self._task: asyncio.Task | None = None
        self._tone: asyncio.Task | None = None
        self._echo_until = 0.0
        self.started_at = 0.0
        self._unavailable = False

    @property
    def speaking(self) -> bool:
        return self._task is not None and not self._task.done()

    def own_audio(self, captured_at: float) -> bool:
        return self.speaking or captured_at <= self._echo_until

    def beep(self, activation: bool = False) -> None:
        if self.config.mode == "silent" or self.speaking or (self._tone and not self._tone.done()):
            return
        self._echo_until = time.perf_counter() + 0.24
        self._tone = asyncio.create_task(self._beep(activation))

    @staticmethod
    async def _beep(activation: bool) -> None:
        try:
            import winsound

            await asyncio.to_thread(winsound.Beep, 930 if activation else 660, 65)
        except (ImportError, RuntimeError):
            pass  # The console still reports activation and completion.

    def say(self, message: str) -> None:
        if self.config.mode == "silent" or self._unavailable:
            return
        self.interrupt()
        # Avoid issuing one of our own standalone stop phrases into the microphone.
        pattern = r"\b(?:" + "|".join(sorted(STOP_WORDS)) + r")\b"
        limit = 420 if self.config.mode == "conversational" else 220
        text = re.sub(pattern, "Halt", message[:limit], flags=re.I)
        text = re.sub(r"\bbestätigen\b", "freigeben", text, flags=re.I)
        self.started_at = time.perf_counter()
        self._task = asyncio.create_task(self._speak(text))

    async def _speak(self, text: str) -> None:
        try:
            if self._voice is None:
                self._voice = WindowsVoice()
            with self.ducking.active():
                await self._voice.speak(text)
        except Exception:
            self._unavailable = True
            self.status(
                "Lokale deutsche Sprachausgabe nicht verfügbar; Konsolenausgabe bleibt aktiv."
            )
        finally:
            self._echo_until = time.perf_counter() + 0.35

    def interrupt(self) -> None:
        if self.speaking:
            self._task.cancel()
            if self._voice is not None:
                try:
                    self._voice.stop()
                except Exception:
                    self.status("Sprachausgabe konnte nicht sofort unterbrochen werden")
            self._echo_until = time.perf_counter() + 0.35

    async def close(self) -> None:
        self.interrupt()
        await asyncio.gather(*(t for t in (self._task, self._tone) if t), return_exceptions=True)
