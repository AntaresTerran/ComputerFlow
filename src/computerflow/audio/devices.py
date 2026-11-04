"""Visible input selection and stable name/host-API binding, without changing Windows defaults."""

import sys
from dataclasses import dataclass
from importlib import import_module

from computerflow.core.config import TriggerConfig
from computerflow.core.errors import ComputerFlowError


def sounddevice():
    try:
        if sys.platform == "win32":
            sys.coinit_flags = 0
            import_module("comtypes")  # Establish MTA before PortAudio.
        return import_module("sounddevice")
    except (ImportError, OSError) as exc:
        raise ComputerFlowError(
            "Audiomodul nicht verfügbar; Desktop-Extra/Frischstart prüfen"
        ) from exc


@dataclass(frozen=True)
class InputDevice:
    id: int
    name: str
    hostapi: str
    default: bool


def input_devices(sd, preferred: bool = False) -> list[InputDevice]:
    try:
        hosts = sd.query_hostapis()
        available = sd.query_devices()
    except Exception as exc:
        raise ComputerFlowError(
            "Audiogeräte konnten nicht gelesen werden; Audio-Treiber prüfen"
        ) from exc
    devices = [
        InputDevice(
            id=i,
            name=d["name"],
            hostapi=hosts[d["hostapi"]]["name"],
            default=i == hosts[d["hostapi"]]["default_input_device"],
        )
        for i, d in enumerate(available)
        if d["max_input_channels"] > 0
    ]
    if preferred and any(d.hostapi == "Windows WASAPI" for d in devices):
        return [d for d in devices if d.hostapi == "Windows WASAPI"]
    return devices


def input_settings(config: TriggerConfig, sd) -> tuple[InputDevice, dict]:
    devices = input_devices(sd)
    if config.device is None:
        matches = [d for d in devices if d.id == sd.default.device[0]]
    elif isinstance(config.device, int):
        matches = [d for d in devices if d.id == config.device]
    else:
        matches = [d for d in devices if d.name.casefold() == config.device.casefold()]
    if config.device_hostapi:
        matches = [d for d in matches if d.hostapi.casefold() == config.device_hostapi.casefold()]
    if len(matches) != 1:
        raise ComputerFlowError(
            "Gespeichertes Mikrofon fehlt oder ist nicht eindeutig. "
            "Mit Start-ComputerFlow.ps1 -Microphone neu auswählen."
        )
    device = matches[0]
    extra = sd.WasapiSettings(auto_convert=True) if device.hostapi == "Windows WASAPI" else None
    kwargs = {
        "device": device.id,
        "channels": 1,
        "dtype": "int16",
        "samplerate": config.sample_rate,
        "extra_settings": extra,
    }
    return device, kwargs


def selected_input(config: TriggerConfig, sd=None) -> InputDevice:
    sd = sd or sounddevice()
    device, kwargs = input_settings(config, sd)
    try:
        sd.check_input_settings(**kwargs)
    except Exception as exc:
        raise ComputerFlowError(
            "Dieses Mikrofon unterstützt den Aufnahmemodus nicht; anderes Gerät/Host-API wählen"
        ) from exc
    return device
