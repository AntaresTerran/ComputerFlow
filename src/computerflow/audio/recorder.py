import io
import threading
import wave
from collections.abc import Callable

from computerflow.audio.devices import input_settings, sounddevice
from computerflow.core.config import TriggerConfig
from computerflow.core.errors import ComputerFlowError


def pcm_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return output.getvalue()


class Recorder:
    def __init__(
        self,
        config: TriggerConfig,
        on_limit: Callable[[], None],
        on_frame: Callable[[bytes, int, bool], None] | None = None,
        ring_seconds: float = 0.0,
    ):
        self.config = config
        self.on_limit = on_limit
        self.on_frame = on_frame
        self._lock = threading.Lock()
        self._data = bytearray()
        self._recording = False
        self._error: str | None = None
        self._stream = None
        self.device_name: str | None = None
        self._limit = config.sample_rate * 2 * config.max_recording_seconds
        self._ring = bytearray()
        self._ring_limit = int(ring_seconds * config.sample_rate) * 2
        self._offset = 0
        self._recording_from = 0

    def open(self) -> None:
        try:
            sd = sounddevice()
            device, kwargs = input_settings(self.config, sd)
            sd.check_input_settings(**kwargs)
            self.device_name = f"{device.name} ({device.hostapi})"
            self._stream = sd.RawInputStream(
                **kwargs,
                blocksize=800,
                callback=self._callback,
            )
            self._stream.start()
        except Exception as exc:
            # PortAudioError derives directly from Exception, not OSError.
            self.close()
            if isinstance(exc, ComputerFlowError):
                raise
            raise ComputerFlowError(
                "Mikrofon nicht verfügbar. Desktop-Extra, Gerätauswahl und "
                "Windows-Mikrofonfreigabe prüfen (computerflow devices)."
            ) from exc

    def _callback(self, indata, frames, time_info, status) -> None:
        notify = False
        with self._lock:
            pcm = bytes(indata) if self._recording or self.on_frame else b""
            offset = self._offset
            self._offset += len(pcm)
            if status:
                self._ring.clear()
            elif self._ring_limit:
                self._ring.extend(pcm)
                del self._ring[: max(0, len(self._ring) - self._ring_limit)]
            if self._recording and status:
                self._error = "Audioaufnahme unterbrochen/überlaufen; bitte erneut aufnehmen"
                self._recording = False
                notify = True
            elif self._recording:
                remaining = self._limit - len(self._data)
                self._data.extend(pcm[:remaining])
                if len(self._data) >= self._limit:
                    self._recording = False
                    notify = True
        if self.on_frame:
            self.on_frame(pcm, offset, bool(status))
        if notify:
            self.on_limit()

    def begin(self, from_offset: int | None = None, *, required_from: int | None = None) -> int:
        with self._lock:
            self._data.clear()
            if from_offset is not None:
                oldest = self._offset - len(self._ring)
                if required_from is not None and oldest <= required_from:
                    from_offset = max(from_offset, oldest)
                index = from_offset - oldest
                if index < 0 or from_offset > self._offset:
                    raise ComputerFlowError("Satzanfang liegt außerhalb des Audiopuffers")
                self._data.extend(self._ring[index:][: self._limit])
            self._error = None
            self._recording = True
            self._recording_from = self._offset if from_offset is None else from_offset
            return self._offset

    def finish_pcm(self, until: int | None = None) -> bytes:
        with self._lock:
            self._recording = False
            error = self._error
            length = len(self._data) if until is None else max(0, until - self._recording_from)
            pcm = bytes(self._data[:length])
            self._data.clear()
            self._error = None
        if error:
            raise ComputerFlowError(error)
        if len(pcm) < self.config.sample_rate * 2 * self.config.min_recording_ms / 1000:
            raise ComputerFlowError("Aufnahme zu kurz; sprich nach der Aktivierung einen Auftrag")
        return pcm

    def finish(self) -> bytes:
        return pcm_to_wav(self.finish_pcm(), self.config.sample_rate)

    def discard(self) -> None:
        with self._lock:
            self._recording = False
            self._data.clear()
            self._ring.clear()
            self._error = None

    def close(self) -> None:
        self.discard()
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
