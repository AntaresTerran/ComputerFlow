import asyncio
import time
from collections.abc import Callable

from computerflow.app import Assistant
from computerflow.audio.ducking import Ducking
from computerflow.audio.feedback import Feedback
from computerflow.audio.recorder import Recorder, pcm_to_wav
from computerflow.audio.speaker import SpeakerVerifier
from computerflow.audio.trigger import KeyboardTrigger
from computerflow.audio.wake import (
    BYTES_PER_SECOND,
    VoiceActivity,
    VoskSource,
    WakeSource,
    pcm_level,
)
from computerflow.core.config import Config
from computerflow.core.errors import Cancelled, ComputerFlowError
from computerflow.core.jobs import Job, State


class VoiceSession:
    def __init__(self, config: Config, assistant: Assistant, status: Callable[[str], None] = print):
        self.config = config
        self.assistant = assistant
        self.status = status
        self.loop = asyncio.get_running_loop()
        self.ducking = Ducking(config.feedback.duck_percent, status)
        self.feedback = Feedback(config.feedback, status, self.ducking)
        self.frames: asyncio.Queue = asyncio.Queue(maxsize=16)
        self.source: WakeSource | None = None
        self.verifier: SpeakerVerifier | None = None
        self.epoch = 0
        use_voice = config.wake.enabled or config.wake.speech_stop
        self.recorder = Recorder(
            config.trigger,
            lambda: self.post(self.finish),
            self._post_frame if use_voice else None,
            config.wake.pre_roll_seconds if config.wake.enabled else 0,
        )
        self.trigger = KeyboardTrigger(
            config.trigger,
            config.execution,
            lambda: self.post(self.start),
            lambda: self.post(self._finish_ptt),
            lambda: self.post(self.cancel),
            lambda: self.post(self._confirm),
        )
        self.recording: Job | None = None
        self.active_job: Job | None = None
        self.task: asyncio.Task | None = None
        self._processing_since = 0.0
        self.timer: asyncio.TimerHandle | None = None
        self.wake_end: int | None = None
        self.last_voice = 0
        self._voice_level = 0.0
        self.wake_command = False

    def post(self, callback, *args) -> None:
        if not self.loop.is_closed():
            self.loop.call_soon_threadsafe(callback, *args)

    def _post_frame(self, pcm: bytes, offset: int, gap: bool) -> None:
        self.post(self._queue_frame, (pcm, offset, gap, time.perf_counter()))

    def _queue_frame(self, frame) -> None:
        if self.frames.full():
            self.frames.get_nowait()
        self.frames.put_nowait(frame)

    def _confirm(self) -> None:
        self.feedback.interrupt()
        self.assistant.confirm()

    def _finish_ptt(self) -> None:
        if self.wake_end is None:
            self.finish()

    def start(self, wake_end: int | None = None) -> None:
        if self.recording or (self.task and not self.task.done()):
            return
        self.epoch += 1
        self.feedback.interrupt()
        self.wake_end = wake_end
        self.wake_command = False
        if wake_end is not None:
            # A little overlap protects the first phoneme after the keyword.
            lead_in = 0.65 if self.verifier else 0.08
            start = max(0, wake_end - round(16000 * lead_in) * 2)
        else:
            start = None
        try:
            self.recorder.begin(start)
        except ComputerFlowError as exc:
            self.wake_end = None
            self.status(str(exc))
            return
        self.recording = self.active_job = Job(self.config.execution.timeout_seconds)
        self.timer = self.loop.call_later(
            min(self.config.trigger.max_recording_seconds, self.recording.remaining), self.finish
        )
        self.ducking.begin()
        self.feedback.beep(activation=True)
        self.status(
            f"[{self.recording.id[:8]}] Aufnahme ({'Computer' if wake_end is not None else 'PTT'})"
        )

    def finish(self) -> None:
        if not self.recording:
            return
        job, self.recording = self.recording, None
        wake_end, self.wake_end = self.wake_end, None
        self.epoch += 1
        self.trigger.recording_finished()
        self._clear_timer()
        self.ducking.end()
        try:
            until = self.last_voice + 7680 if wake_end is not None and self.wake_command else None
            pcm = self.recorder.finish_pcm(until)
            job.check()
        except ComputerFlowError as exc:
            self.status(str(exc))
            self.active_job = None
            return
        if wake_end is not None and not self.wake_command:
            self.active_job = None
            self.status("Kein gesprochener Auftrag nach dem Aktivierungswort erkannt.")
            return
        self._processing_since = time.perf_counter()
        self.task = asyncio.create_task(self._submit(pcm, job, wake_end is not None))
        self.task.add_done_callback(self._task_done)

    async def _submit(self, pcm: bytes, job: Job, from_wake: bool) -> None:
        try:
            if from_wake and self.verifier:
                if not await job.guard(asyncio.to_thread(self.verifier.matches, pcm)):
                    self.status("Stimme nicht sicher erkannt; bei Bedarf Push-to-Talk verwenden.")
                    self.feedback.say("Stimme nicht sicher erkannt.")
                    return
            entry = await self.assistant.run(
                pcm_to_wav(pcm), job, on_confirmation=self.feedback.say
            )
            if job.cancelled.is_set():
                return
            self.feedback.interrupt()
            if (
                self.config.feedback.mode == "conversational"
                or entry.state != State.DONE
                or not entry.executed
            ):
                self.feedback.say(entry.message)
            else:
                self.feedback.beep()
        except Cancelled:
            pass
        finally:
            if self.active_job is job:
                self.active_job = None

    def _task_done(self, task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception():
            self.status("Auftragsverarbeitung beendet; Komponentenstatus prüfen")

    def _clear_timer(self) -> None:
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def cancel(self) -> None:
        self.epoch += 1
        if self.active_job:
            self.active_job.cancel()
        self._clear_timer()
        self.feedback.interrupt()
        self.trigger.recording_finished()
        if self.recording:
            self.recording = None
            self.ducking.end()
        self.wake_end = None
        self.recorder.discard()
        self.assistant.cancel()

    async def _listen_voice(self) -> None:
        assert self.source is not None
        vad = VoiceActivity(self.config.wake.vad_mode)
        silence = int(self.config.wake.silence_seconds * BYTES_PER_SECOND)
        previous_epoch = self.epoch
        while True:
            pcm, offset, gap, captured_at = await self.frames.get()
            stale = time.perf_counter() - captured_at > 0.8
            if self.epoch != previous_epoch or gap or stale:
                self.source.reset()
                self.last_voice = 0
                self._voice_level = 0.0
                previous_epoch = self.epoch
                if gap or stale:
                    continue
            end = offset + len(pcm)
            own_audio = self.feedback.own_audio(captured_at)
            if self.wake_end is not None:
                if (
                    not own_audio
                    and self._foreground_speech(vad, pcm)
                    and end - self.wake_end >= 6400
                ):
                    self.last_voice = end
                    self.wake_command = True
                if end - max(self.last_voice, self.wake_end) >= silence:
                    self.finish()
                continue
            processing = self.task is not None and not self.task.done()
            busy = processing or self.feedback.speaking
            if busy and self.config.wake.speech_stop:
                start = self._processing_since if processing else self.feedback.started_at
                if captured_at <= start:
                    continue
                purpose = "stop"
            elif not busy and not self.recording and self.config.wake.enabled and not own_audio:
                purpose = "wake"
                if self._foreground_speech(vad, pcm):
                    self.last_voice = end
            else:
                self.source.reset()
                continue
            epoch = self.epoch
            try:
                detection = await asyncio.to_thread(self.source.feed, pcm, offset, purpose)
            except Exception as exc:
                raise ComputerFlowError("Lokaler Wake-/Stopp-Erkenner ausgefallen") from exc
            if detection is None or epoch != self.epoch:
                continue
            if purpose == "stop":
                self.status("Sprachstopp erkannt")
                self.cancel()
            else:
                last_voice = self.last_voice
                self.start(min(detection.end, end))
                if self.wake_end is not None and last_voice - self.wake_end >= 6400:
                    self.wake_command = True
                    self.last_voice = last_voice
                previous_epoch = self.epoch

    def _foreground_speech(self, vad: VoiceActivity, pcm: bytes) -> bool:
        self._voice_level *= 0.995
        if not vad.voiced(pcm):
            return False
        # Compared with recent foreground speech, quiet background playback should
        # neither extend the recording indefinitely nor end up in the tail sent to ASR.
        level = pcm_level(pcm)
        self._voice_level = max(level, self._voice_level)
        return level >= self._voice_level * 0.16

    async def run(self) -> None:
        try:
            if self.config.wake.enabled or self.config.wake.speech_stop:
                source = await asyncio.to_thread(VoskSource, self.config)
                self.source = source
                if self.config.wake.verify_speaker:
                    self.verifier = await asyncio.to_thread(SpeakerVerifier, self.config, source)
            self.recorder.open()
            self.status(f"Mikrofon: {self.recorder.device_name}")
            self.trigger.open()
            enabled = []
            if self.config.trigger.enabled:
                enabled.append(f"PTT {self.config.trigger.key} ({self.config.trigger.mode})")
            if self.config.wake.enabled:
                enabled.append("Wake Word „Computer“")
            if self.config.wake.speech_stop:
                enabled.append("Sprachstopp „Stopp“")
            self.status(
                "Bereit: "
                + ", ".join(enabled)
                + f". Not-Aus {self.config.execution.emergency_hotkey}, "
                "F6 Übungsfreigabe, Strg+C beendet."
            )
            if self.source:
                await self._listen_voice()
            else:
                await asyncio.Event().wait()
        finally:
            try:
                self.cancel()
                self.trigger.close()
                self.recorder.close()
            finally:
                if self.task:
                    self.task.cancel()
                    await asyncio.gather(self.task, return_exceptions=True)
                try:
                    await self.feedback.close()
                finally:
                    self.ducking.restore()
