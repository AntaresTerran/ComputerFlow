from collections.abc import Callable
from pathlib import Path

from computerflow.audio.devices import input_devices, selected_input, sounddevice
from computerflow.core.config import Config, TriggerConfig, save_config
from computerflow.core.errors import ComputerFlowError


def configure_microphone(
    config: Config,
    path: Path | None,
    selection: str | None = None,
    read: Callable[[str], str] = input,
    output: Callable[[str], None] = print,
    sd=None,
    list_only: bool = False,
) -> Config:
    sd = sd or sounddevice()
    devices = input_devices(sd, preferred=selection is None)
    output("Aufnahmegerät für ComputerFlow:")
    output("  standard: Windows-Standardgerät verwenden")
    for device in devices:
        marker = " [Windows-Standard]" if device.default else ""
        output(f"  {device.id}: {device.name} — {device.hostapi}{marker}")
    if list_only:
        return config
    while True:
        answer = (
            selection if selection is not None else read("Mikrofon-ID oder standard: ")
        ).strip()
        if answer.casefold() == "standard":
            trigger = config.trigger.model_copy(
                update={
                    "device": None,
                    "device_hostapi": None,
                    "device_selected": True,
                }
            )
        else:
            matches = [d for d in devices if str(d.id) == answer]
            if len(matches) != 1:
                if selection is not None:
                    raise ComputerFlowError(
                        "Unbekannte Mikrofon-ID; microphone --list zeigt die Geräte"
                    )
                output("Bitte eine der angezeigten IDs eingeben.")
                continue
            chosen = matches[0]
            trigger = TriggerConfig.model_validate(
                config.trigger.model_dump()
                | {
                    "device": chosen.name,
                    "device_hostapi": chosen.hostapi,
                    "device_selected": True,
                }
            )
        selected = selected_input(trigger, sd)
        updated = config.model_copy(update={"trigger": trigger})
        saved = save_config(updated, path)
        output(f"Gespeichert: {selected.name} ({selected.hostapi}) in {saved}")
        return updated
