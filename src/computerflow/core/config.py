import os
import re
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from computerflow.core.errors import ComputerFlowError


class ConfigLoader(yaml.SafeLoader):
    """Refuse duplicate keys instead of silently overriding local settings."""


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise yaml.YAMLError("Ungültige oder doppelte Konfigurationsschlüssel")
        result[key] = loader.construct_object(value_node)
    return result


ConfigLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TriggerConfig(StrictModel):
    enabled: bool = True
    key: str = "ctrl_r"
    mode: Literal["hold", "toggle"] = "hold"
    device: int | str | None = None
    device_hostapi: str | None = Field(default=None, min_length=1, max_length=64)
    device_selected: bool = False
    sample_rate: Literal[16000] = 16000
    max_recording_seconds: int = Field(default=30, ge=1, le=60)
    min_recording_ms: int = Field(default=250, ge=50, le=1000)

    @field_validator("key")
    @classmethod
    def valid_key(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9_]{1,24}|vk:[1-9][0-9]{0,2}|mouse:[a-z0-9_]{1,16}", value):
            raise ValueError("Erwarte Tastennamen, vk:Nummer oder mouse:Taste")
        vk = int(value[3:]) if value.startswith("vk:") else 0
        if value in {"f6", "escape", "esc"} or vk in {27, 117} or vk >= 255:
            raise ValueError("Taste ist für Freigabe/Abbruch reserviert oder ungültig")
        return value


class WakeConfig(StrictModel):
    enabled: bool = True
    source: Literal["vosk"] = "vosk"
    model: str | None = None  # Relative to the program directory.
    sensitivity: float = Field(default=0.65, ge=0.1, le=0.95)
    pre_roll_seconds: float = Field(default=2.0, ge=2.0, le=4.0)
    silence_seconds: float = Field(default=1.2, ge=0.4, le=3.0)
    vad_mode: int = Field(default=2, ge=0, le=3)
    speech_stop: bool = True
    verify_speaker: bool = False
    speaker_similarity: float = Field(default=0.70, ge=0.3, le=0.98)


class FeedbackConfig(StrictModel):
    mode: Literal["silent", "brief", "conversational"] = "brief"
    duck_percent: int = Field(default=0, ge=0, le=80)


class ModelConfig(StrictModel):
    backend: Literal["llama_cpp"] = "llama_cpp"
    endpoint: str = "http://127.0.0.1:47831"
    model_id: str = Field(default="LiquidAI/LFM3-Omni-2B-GGUF", min_length=1, max_length=256)
    api_key_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{0,127}$")
    model_revision: str | None = None
    runtime_revision: str | None = None
    model_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    quantization: str | None = None
    request_timeout_seconds: int = Field(default=60, ge=1, le=180)
    max_tokens: int = Field(default=512, ge=64, le=2048)
    max_response_repairs: int = Field(default=1, ge=0, le=1)
    constrained_decoding: bool = True
    prompt_version: Literal["v3"] = "v3"

    @field_validator("endpoint")
    @classmethod
    def local_endpoint(cls, value: str) -> str:
        try:
            url = urlsplit(value)
            port = url.port
        except ValueError as exc:
            raise ValueError("Ungültiger lokaler Server-Endpunkt") from exc
        if (
            url.scheme != "http"
            or url.hostname not in {"127.0.0.1", "::1"}
            or url.username is not None
            or url.password is not None
            or url.path not in {"", "/"}
            or url.query
            or url.fragment
            or port == 0
        ):
            raise ValueError("Nur http://127.0.0.1:PORT oder http://[::1]:PORT erlaubt")
        return value.rstrip("/")


class ExecutionConfig(StrictModel):
    timeout_seconds: int = Field(default=90, ge=5, le=300)
    context_max_age_seconds: int = Field(default=90, ge=5, le=300)
    practice_mode: bool = False
    confirmation_timeout_seconds: int = Field(default=30, ge=5, le=60)
    emergency_hotkey: Literal["ctrl+alt+escape", "ctrl+alt+f12"] = "ctrl+alt+escape"


class RuntimeConfig(StrictModel):
    managed: bool = True
    data_dir: str | None = None
    acceleration: Literal["auto", "vulkan", "cpu"] = "auto"
    device: str | None = Field(default=None, pattern=r"^Vulkan[0-9]+$")
    startup_timeout_seconds: int = Field(default=120, ge=10, le=300)


class Config(StrictModel):
    schema_version: Literal[1] = 1
    trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    wake: WakeConfig = Field(default_factory=WakeConfig)
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    @model_validator(mode="after")
    def audio_activation(self):
        if not (self.trigger.enabled or self.wake.enabled):
            raise ValueError("PTT oder Wake Word muss aktiviert sein")
        if self.wake.verify_speaker and not self.wake.enabled:
            raise ValueError("Stimmprüfung erfordert Wake Word")
        if self.execution.emergency_hotkey.endswith("f12") and self.trigger.key in {
            "f12",
            "vk:123",
        }:
            raise ValueError("PTT kollidiert mit Not-Aus")
        return self


def save_config(config: Config, path: Path | None = None) -> Path:
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    temporary.replace(target)
    return target


def program_root() -> Path:
    configured = os.environ.get("COMPUTERFLOW_HOME")
    if configured:
        return Path(configured).resolve()
    source = Path(__file__).resolve().parents[3]
    if (source / "pyproject.toml").is_file() and (source / "Start-ComputerFlow.ps1").is_file():
        return source
    return Path(sys.prefix).resolve() / "ComputerFlow"


def default_config_path() -> Path:
    return program_root() / "config.yaml"


def load_config(path: Path | None = None) -> Config:
    selected = path or default_config_path()
    if not selected.exists():
        if path is not None:
            raise ComputerFlowError(f"Konfiguration nicht gefunden: {selected}")
        return Config()
    try:
        if selected.stat().st_size > 65536:
            raise ComputerFlowError("Konfigurationsdatei ist größer als 64 KiB")
        raw = yaml.load(selected.read_text(encoding="utf-8"), Loader=ConfigLoader)
        if isinstance(raw, dict) and isinstance(raw.get("model"), dict):
            if raw["model"].get("prompt_version") == "v2":
                raw["model"]["prompt_version"] = "v3"
        return Config.model_validate(raw)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ComputerFlowError("Konfiguration konnte nicht gelesen werden") from exc
    except ValidationError as exc:
        fields = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors())
        raise ComputerFlowError(
            f"Ungültige oder nicht unterstützte Konfiguration: {fields}"
        ) from exc
