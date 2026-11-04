import argparse
import asyncio
import importlib.metadata
import json
import os
import platform
import sys
import tempfile
import unicodedata
from dataclasses import asdict
from pathlib import Path

from computerflow import __version__
from computerflow.app import Assistant
from computerflow.audio.devices import selected_input
from computerflow.audio.selection import configure_microphone
from computerflow.audio.session import VoiceSession
from computerflow.audio.speaker import manage_speaker, profile_path
from computerflow.audio.trigger import KeyboardTrigger
from computerflow.audio.wake import audio_model_ready, install_audio
from computerflow.brain.llama_cpp import LlamaCppBackend
from computerflow.core.config import Config, load_config, program_root
from computerflow.core.errors import ComputerFlowError
from computerflow.core.jobs import Job, State
from computerflow.runtime.manager import (
    ManagedRuntime,
    install,
    lifecycle_lock,
    runtime_root,
    save_setup,
)


def console(message: str) -> None:
    # Window titles and model text cannot inject terminal control sequences.
    safe = "".join(c if unicodedata.category(c)[0] != "C" else " " for c in message)
    print(safe, flush=True)


def desktop_platform():
    from computerflow.platform.windows import WindowsPlatform

    return WindowsPlatform()


def package_versions() -> dict:
    result = {"computerflow": __version__, "python": platform.python_version(), "os": sys.platform}
    for package in ("httpx", "pydantic", "sounddevice", "pynput", "pycaw", "vosk", "winrt-runtime"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = "nicht installiert"
    return result


async def diagnose(config: Config, offline: bool) -> int:
    report = {"versions": package_versions(), "desktop": "nur Windows implementiert"}
    okay = sys.platform == "win32"
    report["data_directory"] = str(runtime_root(config))
    needs_voice = config.wake.enabled or config.wake.speech_stop
    installed = needs_voice and audio_model_ready(config)
    report["voice"] = {
        "ptt": config.trigger.key if config.trigger.enabled else False,
        "wake_word": "Computer" if config.wake.enabled else False,
        "speech_stop": config.wake.speech_stop,
        "local_model_installed": installed,
        "speaker_verifier": config.wake.verify_speaker,
        "speaker_profile_present": profile_path(config).is_file(),
        "feedback": config.feedback.mode,
    }
    if needs_voice and (not installed or report["versions"]["vosk"] == "nicht installiert"):
        okay = False
    if config.wake.verify_speaker and not profile_path(config).is_file():
        okay = False
    if report["versions"]["pynput"] == "nicht installiert":
        report["trigger"] = "Tastaturhook fehlt; Desktop-Extra installieren"
        okay = False
    else:
        report["trigger"] = "pynput installiert; Hook wird erst bei listen/command geöffnet"
    if sys.platform == "win32":
        context = await desktop_platform().snapshot()
        report["desktop"] = {
            "windows_available": bool(context.windows),
            "volume_available": context.volume is not None,
            "media_sessions_available": len(context.media_sessions),
            "unavailable": context.unavailable,
        }
    try:
        device = selected_input(config.trigger)
        report["microphone"] = {
            "name": device.name,
            "hostapi": device.hostapi,
            "status": "16 kHz mono int16 unterstützt; keine Aufnahme durchgeführt",
        }
    except Exception:
        report["microphone"] = "nicht bereit; devices und Windows-Mikrofonfreigabe prüfen"
        okay = False
    if not offline:
        managed = ManagedRuntime(config)
        state = managed.connection() if config.runtime.managed else None
        backend = LlamaCppBackend(
            config.model,
            api_key=state["api_key"] if state else None,
            runtime_info=managed.public_status() if state else None,
        )
        try:
            report["inference"] = await Job(10).guard(backend.probe())
            if report["inference"]["audio_input_reported"] is not True:
                okay = False
        except ComputerFlowError as exc:
            report["inference"] = str(exc)
            okay = False
        finally:
            await backend.close()
    else:
        report["inference"] = "nicht geprüft (--offline)"
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if okay else 1


async def run_assistant(config: Config, args: argparse.Namespace) -> int:
    desktop = desktop_platform()
    managed = ManagedRuntime(config, console)
    state = await asyncio.to_thread(managed.start) if config.runtime.managed else None
    backend = LlamaCppBackend(
        config.model,
        api_key=state["api_key"] if state else None,
        runtime_info=managed.public_status() if state else None,
        on_transcript=lambda text: console(f"Erkannt: {text}"),
    )
    trigger = None
    try:
        runtime = await Job(10).guard(backend.probe())
        console("ComputerFlow " + __version__ + " | " + json.dumps(runtime, ensure_ascii=True))
        assistant = Assistant(config, backend, desktop, console)
        if args.action == "listen":
            if runtime["audio_input_reported"] is not True:
                raise ComputerFlowError(
                    "Server bestätigt keine Audioeingabe. Omni-Modell/Projektor und llama.cpp "
                    "prüfen; computerflow doctor zeigt den gemeldeten Zustand."
                )
            await VoiceSession(config, assistant, console).run()
            return 0
        loop = asyncio.get_running_loop()
        trigger = KeyboardTrigger(
            config.trigger.model_copy(update={"enabled": False}),
            config.execution,
            lambda: None,
            lambda: None,
            lambda: loop.call_soon_threadsafe(assistant.cancel),
            lambda: loop.call_soon_threadsafe(assistant.confirm),
        )
        trigger.open()
        console(f"Not-Aus {config.execution.emergency_hotkey}; F6 Übungsfreigabe")
        entry = await assistant.run(args.text)
        if args.json:
            print(json.dumps(asdict(entry), ensure_ascii=True))
        return 0 if entry.state in {State.DONE, State.WAITING} else 1
    finally:
        if trigger:
            trigger.close()
        await backend.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=f"ComputerFlow {__version__} – lokaler Windows-Assistent"
    )
    parser.add_argument("--version", action="version", version=f"ComputerFlow {__version__}")
    parser.add_argument("--config", type=Path, help="Lokale YAML-Konfiguration")
    sub = parser.add_subparsers(dest="action", required=True)
    doctor = sub.add_parser("doctor", help="Laufzeit und Fähigkeiten prüfen, keine Aufnahme/Aktion")
    doctor.add_argument("--offline", action="store_true", help="Modellserver nicht kontaktieren")
    sub.add_parser("devices", help="Verfügbare Audiogeräte auflisten")
    microphone = sub.add_parser("microphone", help="Mikrofon auswählen und dauerhaft speichern")
    microphone.add_argument("--list", action="store_true", help="Nur Aufnahmegeräte anzeigen")
    microphone.add_argument(
        "--select", help="Geräte-ID oder standard; ohne Angabe interaktive Auswahl"
    )
    sub.add_parser("listen", help="Wake Word, PTT und Ausführung starten (Windows)")
    sub.add_parser("setup", help="Geprüfte lokale Laufzeit, Modell und Projektor einrichten")
    sub.add_parser("audio-setup", help="Lokales Modell für Wake Word und Sprachstopp einrichten")
    speaker = sub.add_parser("speaker", help="Freiwillige lokale Stimmprüfung verwalten")
    speaker.add_argument("operation", choices=["enroll", "status", "delete"])
    server = sub.add_parser("server", help="Lokalen Modellserver verwalten")
    server.add_argument("operation", choices=["start", "status", "stop"])
    command = sub.add_parser(
        "command", help="Einen Textauftrag lokal planen und ausführen (Windows)"
    )
    command.add_argument("text", help="Zum Beispiel: Setze die Systemlautstärke auf 30 Prozent")
    command.add_argument("--json", action="store_true", help="Zusätzlich strukturiertes Ergebnis")
    args = parser.parse_args(argv)
    try:
        if args.config and not args.config.resolve().is_relative_to(program_root()):
            raise ComputerFlowError("Konfiguration muss im ComputerFlow-Ordner liegen")
        config = (
            Config()
            if args.action in {"setup", "microphone"} and args.config and not args.config.exists()
            else load_config(args.config)
        )
        if not runtime_root(config).is_relative_to(program_root()):
            raise ComputerFlowError(
                "Datenordner liegt außerhalb von ComputerFlow. Für den Umstieg von 0.0.1 "
                "siehe README, Abschnitt Datenordner."
            )
        temporary = runtime_root(config) / "temp"
        temporary.mkdir(parents=True, exist_ok=True)
        for name in ("TEMP", "TMP", "TMPDIR"):
            os.environ[name] = str(temporary)
        tempfile.tempdir = str(temporary)
        if args.action == "microphone":
            configure_microphone(
                config, args.config, args.select, output=console, list_only=args.list
            )
            return 0
        if args.action == "speaker":
            manage_speaker(config, args.config, args.operation, console)
            return 0
        if args.action == "audio-setup":
            install_audio(config, console)
            return 0
        if (
            args.action in {"setup", "listen"}
            and not config.trigger.device_selected
            and config.trigger.device is None
            and sys.stdin.isatty()
        ):
            config = configure_microphone(config, args.config, output=console)
        if args.action == "setup":
            install_audio(config, console)
            if config.runtime.managed:
                with lifecycle_lock(runtime_root(config)):
                    profile = install(config, console)
                    target = save_setup(config, profile, args.config)
                console(f"Konfiguration gespeichert: {target}")
            return 0
        if args.action == "server":
            managed = ManagedRuntime(config, console)
            if args.operation == "start":
                managed.start()
            elif args.operation == "stop":
                console("Modellserver beendet" if managed.stop() else "Kein eigener Server aktiv")
            print(json.dumps(managed.public_status(), ensure_ascii=True, indent=2))
            return 0
        if args.action == "devices":
            try:
                import sounddevice as sd

                console(str(sd.query_devices()))
                return 0
            except Exception as exc:
                raise ComputerFlowError(
                    "Audiogeräte nicht lesbar; Desktop-Extra installieren"
                ) from exc
        if args.action == "doctor":
            return asyncio.run(diagnose(config, args.offline))
        return asyncio.run(run_assistant(config, args))
    except ComputerFlowError as exc:
        console(f"Fehler: {exc}")
        return 1
    except OSError:
        console(
            "Fehler: Lokale Datei/Gerät nicht verfügbar. Pfade und Schreibrechte prüfen; "
            "gegebenenfalls computerflow setup erneut ausführen."
        )
        return 1
    except (KeyboardInterrupt, EOFError):
        console("ComputerFlow beendet")
        return 130
