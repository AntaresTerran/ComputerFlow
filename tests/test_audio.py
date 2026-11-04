import io
import sys
import wave
from types import SimpleNamespace

import pytest

from computerflow.audio.ducking import Ducking
from computerflow.audio.recorder import Recorder
from computerflow.audio.trigger import KeyboardTrigger
from computerflow.core.config import ExecutionConfig, TriggerConfig
from computerflow.core.errors import ComputerFlowError


def test_recorder_is_bounded_and_wav_stays_in_memory():
    limits = []
    recorder = Recorder(TriggerConfig(max_recording_seconds=1), lambda: limits.append(True))
    recorder.begin()
    recorder._callback(b"\x00\x00" * 20000, 20000, None, False)
    recorder._callback(b"\x01\x01" * 20000, 20000, None, False)
    data = recorder.finish()
    with wave.open(io.BytesIO(data), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16000
        assert wav.getsampwidth() == 2
        assert wav.getnframes() == 16000
    assert limits == [True]
    assert not recorder._data


def test_audio_overflow_invalidates_entire_command():
    recorder = Recorder(TriggerConfig(), lambda: None)
    recorder.begin()
    recorder._callback(b"\x00\x00" * 8000, 8000, None, False)
    recorder._callback(b"", 0, None, True)
    with pytest.raises(ComputerFlowError, match="überlaufen"):
        recorder.finish()
    assert not recorder._data


def test_discard_clears_audio_and_short_recording_is_rejected():
    recorder = Recorder(TriggerConfig(), lambda: None)
    recorder.begin()
    recorder._callback(b"\x00\x00" * 100, 100, None, False)
    recorder.discard()
    assert not recorder._data
    with pytest.raises(ComputerFlowError, match="zu kurz"):
        recorder.finish()


def test_ring_preloads_speech_after_the_keyword_once():
    recorder = Recorder(TriggerConfig(), lambda: None, lambda *_: None, 2)
    prefix, first, second = (bytes([number, 0]) * 8000 for number in (1, 2, 3))
    recorder._callback(prefix, 8000, None, False)
    recorder._callback(first, 8000, None, False)
    recorder.begin(len(prefix))
    recorder._callback(second, 8000, None, False)
    assert recorder.finish_pcm() == first + second
    recorder.discard()
    with pytest.raises(ComputerFlowError, match="Audiopuffer"):
        recorder.begin(len(prefix))


def test_portaudio_errors_are_reported_without_raw_exception(monkeypatch):
    class PortAudioError(Exception):
        pass

    def fail(**kwargs):
        raise PortAudioError("private driver detail")

    monkeypatch.setitem(
        __import__("sys").modules,
        "sounddevice",
        SimpleNamespace(
            query_hostapis=lambda: [{"name": "MME", "default_input_device": 0}],
            query_devices=lambda: [
                {"name": "Test microphone", "hostapi": 0, "max_input_channels": 1}
            ],
            default=SimpleNamespace(device=(0, 0)),
            check_input_settings=fail,
        ),
    )
    recorder = Recorder(TriggerConfig(), lambda: None)
    with pytest.raises(ComputerFlowError, match="Mikrofon nicht verfügbar") as error:
        recorder.open()
    assert "private driver detail" not in str(error.value)
    assert not recorder._data


def simulated_trigger(mode="hold"):
    events = []
    trigger = KeyboardTrigger(
        TriggerConfig(mode=mode),
        ExecutionConfig(),
        lambda: events.append("start"),
        lambda: events.append("finish"),
        lambda: events.append("cancel"),
        lambda: events.append("confirm"),
    )
    keys = ["ctrl", "ctrl_l", "ctrl_r", "alt", "alt_l", "alt_r", "alt_gr", "esc", "f12", "f6"]
    trigger._keyboard = SimpleNamespace(Key=SimpleNamespace(**{key: key for key in keys}))
    trigger._key = "ctrl_r"
    return trigger, events


def test_hold_release_finishes_once_and_key_repeat_is_ignored():
    trigger, events = simulated_trigger()
    trigger._press("ctrl_r")
    trigger._press("ctrl_r")
    assert events == ["start"]
    trigger._release("ctrl_r")
    trigger._release("ctrl_r")
    assert events == ["start", "finish"]


def test_toggle_finishes_on_second_press():
    trigger, events = simulated_trigger("toggle")
    trigger._press("ctrl_r")
    trigger._release("ctrl_r")
    trigger._press("ctrl_r")
    assert events == ["start", "finish"]


def test_emergency_hotkey_cancels_without_finishing_recording():
    trigger, events = simulated_trigger()
    for key in ["ctrl_r", "alt_l", "esc"]:
        trigger._press(key)
    trigger._release("ctrl_r")
    assert events == ["start", "cancel"]


def test_mouse_hold_uses_the_same_capture_callbacks():
    trigger, events = simulated_trigger()
    trigger.config = TriggerConfig(key="mouse:x2")
    trigger._mouse_button = "x2"
    trigger._click(0, 0, "x1", True)
    trigger._click(0, 0, "x2", True)
    trigger._click(0, 0, "x2", False)
    assert events == ["start", "finish"]


def test_ducking_restores_its_own_change_but_preserves_manual_volume(monkeypatch):
    class Volume:
        level = 0.8

        def GetMasterVolume(self):
            return self.level

        def SetMasterVolume(self, level, context):
            self.level = level

    untouched, adjusted = Volume(), Volume()
    sessions = [
        SimpleNamespace(ProcessId=123, SimpleAudioVolume=untouched),
        SimpleNamespace(ProcessId=456, SimpleAudioVolume=adjusted),
    ]
    pycaw = SimpleNamespace(AudioUtilities=SimpleNamespace(GetAllSessions=lambda: sessions))
    monkeypatch.setitem(sys.modules, "pycaw.pycaw", pycaw)
    ducking = Ducking(50, lambda _: None)
    with pytest.raises(RuntimeError), ducking.active():
        assert untouched.level == adjusted.level == 0.4
        adjusted.level = 0.6
        raise RuntimeError
    assert untouched.level == 0.8
    assert adjusted.level == 0.6
