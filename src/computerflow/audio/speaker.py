"""Optional local voice matching. Only enrolled numerical vectors persist."""

import json
import math
import sys
import threading
from pathlib import Path

from computerflow.audio.recorder import Recorder
from computerflow.audio.wake import VoskSource, install_audio, model_path
from computerflow.core.config import Config, save_config
from computerflow.core.errors import ComputerFlowError
from computerflow.platform.protection import protect, unprotect
from computerflow.runtime.artifacts import SPEAKER_MODEL
from computerflow.runtime.manager import read_json, runtime_root, write_json


def profile_path(config: Config) -> Path:
    return runtime_root(config) / "profiles" / "speaker.tmp"


def unit_vector(values) -> tuple[float, ...]:
    if len(values) != 128 or any(type(value) not in {float, int} for value in values):
        raise ValueError("Invalid embedding")
    norm = math.hypot(*values)
    if not math.isfinite(norm) or norm == 0:
        raise ValueError("Invalid embedding")
    return tuple(value / norm for value in values)


class SpeakerVerifier:
    def __init__(self, config: Config, source: VoskSource, *, enrolling=False):
        try:
            from vosk import KaldiRecognizer, SpkModel

            self._recognizer = KaldiRecognizer
            self._speaker_model = SpkModel(str(model_path(config, speaker=True)))
            self._asr_model = source.model
        except Exception as exc:
            raise ComputerFlowError("Lokales Stimmprüfmodell fehlt oder ist ungültig") from exc
        self.threshold = config.wake.speaker_similarity
        self.samples: tuple[tuple[float, ...], ...] = ()
        if not enrolling:
            path = profile_path(config)
            try:
                if path.stat().st_size > 32000:
                    raise ValueError
                envelope = read_json(path) or {}
                profile = json.loads(unprotect(envelope["protected_profile"]))
                if profile["model"] != SPEAKER_MODEL.sha256 or len(profile["samples"]) != 3:
                    raise ValueError
                self.samples = tuple(unit_vector(sample) for sample in profile["samples"])
            except (ValueError, TypeError, KeyError, OSError) as exc:
                raise ComputerFlowError(
                    "Stimmprofil fehlt oder ist ungültig; speaker enroll"
                ) from exc

    def embedding(self, pcm: bytes) -> tuple[float, ...] | None:
        recognizer = self._recognizer(self._asr_model, 16000, self._speaker_model)
        recognizer.AcceptWaveform(pcm)
        result = json.loads(recognizer.FinalResult())
        try:
            if result.get("spk_frames", 0) >= 75:
                return unit_vector(result["spk"])
        except (ValueError, KeyError, TypeError):
            pass
        return None

    def matches(self, pcm: bytes) -> bool:
        candidate = self.embedding(pcm)
        if candidate is None:
            return False
        scores = sorted(
            sum(x * y for x, y in zip(candidate, sample, strict=True)) for sample in self.samples
        )
        return scores[1] >= self.threshold


def manage_speaker(config: Config, path: Path | None, operation: str, console) -> None:
    target = profile_path(config)
    if operation == "status":
        state = "aktiv" if config.wake.verify_speaker else "aus"
        console(
            f"Stimmprüfung: {state}. Lokales Profil: {'vorhanden' if target.is_file() else 'fehlt'}"
        )
        return
    enabled = operation == "enroll"
    data = config.model_dump(mode="json")
    data["wake"]["verify_speaker"] = enabled
    if enabled:
        if not sys.stdin.isatty() or not config.wake.enabled:
            raise ComputerFlowError(
                "Stimmprofil bitte interaktiv mit aktiviertem Wake Word anlegen"
            )
        install_audio(config, console, speaker=True)
        verifier = SpeakerVerifier(config, VoskSource(config), enrolling=True)
        samples = []
        recorder = Recorder(config.trigger, lambda: None)
        duration = min(config.trigger.max_recording_seconds, 5)
        if duration < 3:
            raise ComputerFlowError("Stimmprofil braucht eine Aufnahmegrenze von mindestens 3 s")
        recorder.open()
        try:
            for index in range(3):
                input(
                    f"{index + 1}/3: Enter drücken, dann {duration} s frei auf Deutsch sprechen. "
                )
                recorder.begin()
                console("Aufnahme läuft")
                threading.Event().wait(duration)
                vector = verifier.embedding(recorder.finish_pcm())
                if vector is None:
                    raise ComputerFlowError(
                        "Zu wenig klare Sprache; Stimmprofil bitte erneut anlegen"
                    )
                samples.append(vector)
        finally:
            recorder.close()
        payload = json.dumps({"model": SPEAKER_MODEL.sha256, "samples": samples}).encode("utf-8")
        write_json(target, {"protected_profile": protect(payload)})
        save_config(Config.model_validate(data), path)
        console("Stimmprofil gespeichert und für Wake-Aufträge aktiviert")
    else:
        save_config(Config.model_validate(data), path)
        target.unlink(missing_ok=True)
        console("Stimmprofil gelöscht und Stimmprüfung deaktiviert")
