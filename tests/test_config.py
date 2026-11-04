from pathlib import Path

import pytest
from pydantic import ValidationError

from computerflow.core.config import Config, ModelConfig, load_config
from computerflow.core.errors import ComputerFlowError


def test_defaults_and_example_are_supported():
    config = load_config(Path(__file__).parents[1] / "config.example.yaml")
    assert config.trigger.key == "ctrl_r"
    assert config.model.backend == "llama_cpp"
    assert config.trigger.sample_rate == 16000


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1:8080",
        "http://example.com",
        "http://localhost:8080",
        "http://127.0.0.1.evil.test",
        "http://127.0.0.1:8080/v1",
        "http://secret@127.0.0.1",
        "http://127.0.0.1?remote=1",
        "http://127.0.0.1#x",
        "http://127.0.0.1:0",
        "http://[::1]:invalid",
    ],
)
def test_remote_or_ambiguous_endpoints_rejected(endpoint):
    with pytest.raises(ValidationError):
        ModelConfig(endpoint=endpoint)


def test_ipv6_loopback():
    assert ModelConfig(endpoint="http://[::1]:8080/").endpoint == "http://[::1]:8080"


@pytest.mark.parametrize(
    "value",
    [
        {"model": {"mock_mode": True}},
        {"trigger": {"mode": "wake_word"}},
        {"execution": {"timeout_seconds": 0}},
        {"trigger": {"sample_rate": 44100}},
        {"trigger": {"max_recording_seconds": "30"}},
        {"panel": {"enabled": True}},
    ],
)
def test_unsupported_or_coerced_configuration_is_rejected(value):
    with pytest.raises(ValidationError):
        Config.model_validate(value)


def test_yaml_errors_do_not_echo_private_values(tmp_path):
    file = tmp_path / "config.yaml"
    file.write_text("model:\n  endpoint: http://private-token@example.com\n", encoding="utf-8")
    with pytest.raises(ComputerFlowError) as error:
        load_config(file)
    assert "private-token" not in str(error.value)
    assert "model.endpoint" in str(error.value)


def test_yaml_python_object_is_never_loaded(tmp_path):
    file = tmp_path / "config.yaml"
    file.write_text("!!python/object/apply:os.system ['never-run']", encoding="utf-8")
    with pytest.raises(ComputerFlowError):
        load_config(file)


def test_explicit_missing_config_fails(tmp_path):
    with pytest.raises(ComputerFlowError, match="nicht gefunden"):
        load_config(tmp_path / "missing.yaml")


def test_duplicate_yaml_keys_rejected(tmp_path):
    file = tmp_path / "config.yaml"
    file.write_text("execution:\n  practice_mode: true\n  practice_mode: false\n", encoding="utf-8")
    with pytest.raises(ComputerFlowError):
        load_config(file)
