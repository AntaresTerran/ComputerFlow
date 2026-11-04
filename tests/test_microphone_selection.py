from types import SimpleNamespace

import pytest

from computerflow.audio.devices import input_settings
from computerflow.audio.selection import configure_microphone
from computerflow.core.config import Config, TriggerConfig, load_config
from computerflow.core.errors import ComputerFlowError


def devices(names=("Headset microphone", "Webcam microphone")):
    checked = []
    api = SimpleNamespace(
        query_devices=lambda: [
            {"name": name, "hostapi": 0, "max_input_channels": 1} for name in names
        ],
        query_hostapis=lambda: [{"name": "Windows WASAPI", "default_input_device": 0}],
        default=SimpleNamespace(device=(0, 0)),
        WasapiSettings=lambda **kwargs: kwargs,
        check_input_settings=lambda **kwargs: checked.append(kwargs),
    )
    return api, checked


def test_webcam_selection_is_saved_by_name_and_api_without_changing_system_default(tmp_path):
    sd, checked = devices()
    path = tmp_path / "config.yaml"
    selected = configure_microphone(Config(), path, "1", sd=sd, output=lambda _: None)
    loaded = load_config(path)
    assert loaded == selected
    assert loaded.trigger.device == "Webcam microphone"
    assert loaded.trigger.device_hostapi == "Windows WASAPI"
    assert loaded.trigger.device_selected
    assert checked[0]["device"] == 1
    assert checked[0]["extra_settings"] == {"auto_convert": True}
    assert sd.default.device == (0, 0)


def test_saved_device_survives_device_index_reordering():
    config = TriggerConfig(device="Webcam microphone", device_hostapi="Windows WASAPI")
    sd, _ = devices(("Webcam microphone", "Headset microphone"))
    chosen, kwargs = input_settings(config, sd)
    assert chosen.name == "Webcam microphone" and kwargs["device"] == 0


@pytest.mark.parametrize(
    "names", [("Headset microphone",), ("Webcam microphone", "Webcam microphone")]
)
def test_missing_or_ambiguous_saved_device_never_falls_back_to_another_microphone(names):
    sd, _ = devices(names)
    with pytest.raises(ComputerFlowError, match="fehlt oder ist nicht eindeutig"):
        input_settings(
            TriggerConfig(device="Webcam microphone", device_hostapi="Windows WASAPI"), sd
        )


def test_choice_of_windows_default_is_remembered(tmp_path):
    sd, _ = devices()
    config = configure_microphone(
        Config(), tmp_path / "config.yaml", "standard", sd=sd, output=lambda _: None
    )
    assert config.trigger.device is None and config.trigger.device_selected


def test_invalid_selection_never_overwrites_configuration(tmp_path):
    sd, _ = devices()
    path = tmp_path / "config.yaml"
    path.write_text("schema_version: 1\n", encoding="utf-8")
    with pytest.raises(ComputerFlowError):
        configure_microphone(Config(), path, "999", sd=sd, output=lambda _: None)
    assert path.read_text(encoding="utf-8") == "schema_version: 1\n"


def test_list_is_read_only(tmp_path):
    sd, checked = devices()
    path = tmp_path / "config.yaml"
    configure_microphone(Config(), path, sd=sd, list_only=True, output=lambda _: None)
    assert not path.exists() and not checked


def test_device_enumeration_failure_is_controlled(tmp_path):
    sd, _ = devices()

    def fail():
        raise RuntimeError("private driver diagnostic")

    sd.query_devices = fail
    with pytest.raises(
        ComputerFlowError, match="Audiogeräte konnten nicht gelesen werden"
    ) as error:
        configure_microphone(Config(), tmp_path / "config.yaml", sd=sd, list_only=True)
    assert "private driver diagnostic" not in str(error.value)
