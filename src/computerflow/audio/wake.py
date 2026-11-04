"""Local streaming keywords and endpoint detection, independent of the planner."""

import json
import math
from array import array
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from computerflow.core.config import Config, program_root
from computerflow.core.errors import ComputerFlowError
from computerflow.runtime.artifacts import (
    SPEAKER_MODEL,
    WAKE_MODEL,
    download,
    extract_verified_zip,
)
from computerflow.runtime.manager import lifecycle_lock, runtime_root

Purpose = Literal["wake", "stop"]
STOP_WORDS = {"stop", "stopp", "abbrechen"}
BYTES_PER_SECOND = 32000


def model_path(config: Config, *, speaker: bool = False) -> Path:
    artifact = SPEAKER_MODEL if speaker else WAKE_MODEL
    if config.wake.model and not speaker:
        root = program_root()
        model = (root / config.wake.model).resolve()
        if not model.is_relative_to(root):
            raise ComputerFlowError("Wake-Word-Modell muss im ComputerFlow-Ordner liegen")
        return model
    return runtime_root(config) / "models" / Path(artifact.name).stem


def audio_model_ready(config: Config, *, speaker: bool = False) -> bool:
    path = model_path(config, speaker=speaker)
    if speaker:
        needed = ("final.ext.raw", "mean.vec", "transform.mat", "mfcc.conf")
        expected = SPEAKER_MODEL.sha256
    else:
        needed = ("am/final.mdl", "conf/model.conf", "graph/HCLr.fst", "graph/Gr.fst")
        expected = WAKE_MODEL.sha256
    if not all((path / name).is_file() for name in needed):
        return False
    if config.wake.model and not speaker:
        return True
    marker = path / ".verified"
    try:
        return marker.read_text(encoding="ascii") == expected
    except (OSError, UnicodeError):
        return False


def install_audio(config: Config, progress: Callable[[str], None], *, speaker=False) -> None:
    if not (config.wake.enabled or config.wake.speech_stop or speaker):
        return
    root = runtime_root(config)
    with lifecycle_lock(root):
        for use_speaker in (False, True) if speaker or config.wake.verify_speaker else (False,):
            if audio_model_ready(config, speaker=use_speaker):
                continue
            if config.wake.model and not use_speaker:
                raise ComputerFlowError(
                    "Konfiguriertes lokales Vosk-Modell fehlt oder ist ungültig"
                )
            artifact = SPEAKER_MODEL if use_speaker else WAKE_MODEL
            archive = download(artifact, root / "downloads", progress)
            extract_verified_zip(archive, root / "models")
            marker = model_path(config, speaker=use_speaker) / ".verified"
            marker.write_text(artifact.sha256, encoding="ascii")


@dataclass(frozen=True)
class Detection:
    end: int  # Absolute byte position in the current microphone stream.


class WakeSource(Protocol):
    def feed(self, pcm: bytes, offset: int, purpose: Purpose) -> Detection | None: ...
    def reset(self) -> None: ...


class VoiceActivity:
    def __init__(self, mode: int):
        import webrtcvad

        self._vad = webrtcvad.Vad(mode)

    def voiced(self, pcm: bytes) -> bool:
        # WebRTC VAD accepts exact 10 ms frames at 16 kHz.
        return (
            sum(self._vad.is_speech(pcm[i : i + 320], 16000) for i in range(0, len(pcm) - 319, 320))
            >= 2
        )


def pcm_level(pcm: bytes) -> int:
    samples = array("h", pcm)
    return math.isqrt(sum(value * value for value in samples) // len(samples)) if samples else 0


class VoskSource:
    def __init__(self, config: Config):
        if not audio_model_ready(config):
            raise ComputerFlowError("Lokales Audiomodell fehlt; audio-setup ausführen")
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel

            SetLogLevel(-1)
            self.model = Model(str(model_path(config)))
            self._recognizer = KaldiRecognizer
        except Exception as exc:
            raise ComputerFlowError(
                "Lokaler Wake-/Stopp-Erkenner nicht verfügbar; audio-setup ausführen"
            ) from exc
        self.sensitivity = config.wake.sensitivity
        self.vad_mode = config.wake.vad_mode
        self.reset()

    def reset(self) -> None:
        self._stream = None
        self._purpose = None
        self._start = 0
        self._end = 0
        self._last_voice = 0
        self._next_partial = 0
        self._stop_audio = bytearray()
        self._vad = None

    def feed(self, pcm: bytes, offset: int, purpose: Purpose) -> Detection | None:
        if self._purpose != purpose or self._end != offset:
            self.reset()
            self._stream = self._recognizer(self.model, 16000)
            self._stream.SetWords(True)
            self._stream.SetPartialWords(True)
            self._start, self._purpose = offset, purpose
            self._vad = VoiceActivity(self.vad_mode)
        self._end = offset + len(pcm)
        if self._vad.voiced(pcm):
            self._last_voice = self._end
        if purpose == "stop":
            self._stop_audio.extend(pcm)
        final = self._stream.AcceptWaveform(pcm)
        quiet = self._last_voice and self._end - self._last_voice >= 9600
        expired = self._end - self._start >= 8 * BYTES_PER_SECOND
        if final:
            result = json.loads(self._stream.Result())
        elif quiet or expired:
            result = json.loads(self._stream.FinalResult())
            final = True
        elif purpose == "wake" and self._end >= self._next_partial:
            self._next_partial = self._end + 4800
            result = json.loads(self._stream.PartialResult())
        else:
            return None
        words = result.get("result" if final else "partial_result", [])
        detection = self._detect(words, purpose)
        if final or detection:
            self.reset()
        return detection

    def _detect(self, words: list[dict], purpose: Purpose) -> Detection | None:
        if not words:
            return None
        threshold = 1.0 - self.sensitivity
        if purpose == "wake":
            previous_end = 0.0
            for index, word in enumerate(words):
                clear_boundary = not index or word["start"] - previous_end >= 0.35
                # A faint concurrent voice can decode as a tiny token immediately before
                # the keyword. Keep the boundary for ordinary sentences.
                short_leading_token = (
                    index == 1 and previous_end - words[0]["start"] <= 0.12 and word["conf"] >= 0.80
                )
                if word["word"] == "computer" and (clear_boundary or short_leading_token):
                    if word["conf"] >= threshold:
                        return Detection(self._start + 2 * round(word["end"] * 16000))
                previous_end = word["end"]
            return None
        names = [word["word"] for word in words]
        if names[0] == "computer":
            names = names[1:]
        if len(names) == 1 and names[0] in STOP_WORDS | {"shop"}:
            word = words[-1]
            confidence = 0.48
            if names[0] == "shop":
                if not self._confirms_stop():
                    return None
                confidence = 0.32
            if word["conf"] >= confidence:
                return Detection(self._start + 2 * round(word["end"] * 16000))
        return None

    def _confirms_stop(self) -> bool:
        # The German full-vocabulary model occasionally decodes spoken "Stopp" as
        # "Shop". A second, biased decode is only consulted for that isolated word.
        rec = self._recognizer(
            self.model, 16000, json.dumps(["stopp", "stop", "computer stopp", "[unk]"])
        )
        rec.SetWords(True)
        rec.AcceptWaveform(bytes(self._stop_audio))
        result = json.loads(rec.FinalResult()).get("result", [])
        return bool(
            result and result[-1]["word"] in {"stopp", "stop"} and result[-1]["conf"] >= 0.60
        )
