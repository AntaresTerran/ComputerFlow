"""Opt-in real Windows/model acceptance with owned windows and a silent player.

Run create_validation_audio.ps1 first. Never touches another app's playback.
Synthetic speech enters the actual bounded PTT recorder; microphone and hook
availability are checked separately. No personal microphone audio is saved.
"""

import asyncio
import ctypes
import json
import sys
import time
import tkinter as tk
import wave
from pathlib import Path

import httpx
import psutil

from computerflow.app import Assistant
from computerflow.audio.recorder import Recorder
from computerflow.audio.trigger import KeyboardTrigger
from computerflow.brain.llama_cpp import LlamaCppBackend
from computerflow.cli import PushToTalkSession
from computerflow.core.config import Config, ExecutionConfig, load_config
from computerflow.core.jobs import State
from computerflow.platform.windows import WindowsPlatform
from computerflow.runtime.manager import ManagedRuntime

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / ".computerflow/validation"


async def validate(config: Config, interactive: bool = False) -> dict:
    desktop = WindowsPlatform()
    original_foreground = desktop.user32.GetForegroundWindow()
    original_device = desktop._speakers()
    original_level = original_device.EndpointVolume.GetMasterVolumeLevelScalar()
    runtime = ManagedRuntime(config)
    state = await asyncio.to_thread(runtime.start)
    backend = LlamaCppBackend(
        config.model,
        api_key=state["api_key"],
        runtime_info=runtime.public_status(),
    )
    report = {"environment": runtime.public_status(), "cases": []}
    gui = tk.Tk()
    gui.title("ComputerFlow Testfenster Alpha")
    gui.geometry("380x120+80+80")
    beta = tk.Toplevel(gui)
    beta.title("ComputerFlow Testfenster Beta")
    beta.geometry("380x120+480+80")
    player = None
    pump = None

    def record(name, elapsed=0, **details):
        report["cases"].append(
            {"name": name, "passed": True, "seconds": round(elapsed, 3), **details}
        )
        print("PASS", name, flush=True)

    async def ui_pump():
        while True:
            gui.update()
            await asyncio.sleep(0.01)

    async def run_ptt(name: str, assistant: Assistant):
        session = PushToTalkSession(config, assistant)
        with wave.open(str(AUDIO / f"{name}.wav"), "rb") as wav:
            assert wav.getframerate() == 16000 and wav.getnchannels() == 1
            session.start()
            while pcm := wav.readframes(800):
                session.recorder._callback(pcm, len(pcm) // 2, None, False)
                await asyncio.sleep(0)
        session.finish()
        return await session.task

    try:
        gui.update()
        pump = asyncio.create_task(ui_pump())
        if interactive:
            start = asyncio.Event()
            tk.Button(beta, text="Abnahme starten", command=start.set).pack(pady=25)
            print("READY: Im Testfenster Beta auf Abnahme starten klicken", flush=True)
            await asyncio.wait_for(start.wait(), 120)
        beta.focus_force()
        await asyncio.sleep(0.1)
        assistant = Assistant(config, backend, desktop)
        start = time.monotonic()
        result = await run_ptt("volume", assistant)
        assert result.state == State.DONE, result
        actual = desktop._speakers().EndpointVolume.GetMasterVolumeLevelScalar() * 100
        assert abs(actual - 39) <= 1, actual
        record(
            "synthetic_speech_ptt_to_real_system_volume",
            time.monotonic() - start,
            actual_percent=round(actual),
        )

        start = time.monotonic()
        result = await run_ptt("focus", assistant)
        assert result.state == State.DONE, result
        foreground = desktop._window(desktop.user32.GetForegroundWindow())
        assert foreground.title == "ComputerFlow Testfenster Alpha", foreground
        record("synthetic_speech_ptt_to_real_window_focus", time.monotonic() - start)

        start = time.monotonic()
        result = await run_ptt("ambiguous", assistant)
        assert result.state == State.WAITING and not result.executed, result
        record("ambiguous_windows_require_clarification", time.monotonic() - start)
        # Finish the clarification, proving a fresh context is used for the reply.
        result = await assistant.run("Wechsle zum ComputerFlow Testfenster Beta.")
        assert result.state == State.DONE, result
        record("clarification_followup_executes_exact_window")

        ctypes.WinDLL("shell32").SetCurrentProcessExplicitAppUserModelID("ComputerFlow.Testplayer")
        from winrt.windows.foundation import Uri
        from winrt.windows.media.core import MediaSource
        from winrt.windows.media.playback import MediaPlayer

        silence = AUDIO / "silence.wav"
        with wave.open(str(silence), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\0\0" * 16000 * 20)
        player = MediaPlayer()
        player.volume = 0.0
        player.is_looping_enabled = True
        player.source = MediaSource.create_from_uri(Uri(silence.as_uri()))
        player.play()
        await asyncio.sleep(0.3)
        for case, desired in (("pause", "paused"), ("play", "playing")):
            start = time.monotonic()
            result = await run_ptt(case, assistant)
            assert result.state == State.DONE, result
            context = await desktop.snapshot()
            own = next(s for s in context.media_sessions if s.app == "ComputerFlow.Testplayer")
            assert own.status == desired, own
            record(f"synthetic_speech_ptt_to_real_media_{case}", time.monotonic() - start)

        result = await run_ptt("stop", assistant)
        assert result.state == State.CANCELLED and not result.executed, result
        record("spoken_stop_is_never_planned_as_action")

        practice_config = config.model_copy(
            update={
                "execution": ExecutionConfig(practice_mode=True),
            }
        )
        waiting = asyncio.Event()
        practice = Assistant(
            practice_config,
            backend,
            desktop,
            lambda message: waiting.set() if "Übungsfreigabe" in message else None,
        )
        task = asyncio.create_task(practice.run("Setze die Systemlautstärke auf 38 Prozent."))
        await asyncio.wait_for(waiting.wait(), 30)
        assert not practice.current.executed
        practice.confirm()
        assert (await task).state == State.DONE
        record("live_action_waits_for_bound_practice_approval")

        request_started = asyncio.Event()

        async def on_request(request):
            if request.url.path == "/v1/chat/completions":
                request_started.set()

        client = httpx.AsyncClient(
            base_url=config.model.endpoint,
            headers={"Authorization": "Bearer " + state["api_key"]},
            timeout=60,
            trust_env=False,
            event_hooks={"request": [on_request]},
        )
        cancellable = LlamaCppBackend(config.model, client)
        try:
            control = Assistant(config, cancellable, desktop, lambda _: None)
            task = asyncio.create_task(control.run("Setze die Systemlautstärke auf 37 Prozent."))
            await asyncio.wait_for(request_started.wait(), 30)
            control.cancel()
            result = await task
            assert result.state == State.CANCELLED and not result.executed
            record("cancel_live_model_request_discards_action")

            request_started.clear()
            task = asyncio.create_task(control.run("Setze die Systemlautstärke auf 36 Prozent."))
            await asyncio.wait_for(request_started.wait(), 30)
            gui.focus_force()
            await asyncio.sleep(0.1)
            result = await task
            assert result.state == State.CANCELLED and not result.executed, result
            record("manual_focus_change_cancels_live_planning")
        finally:
            await cancellable.close()

        recorder = Recorder(config.trigger, lambda: None)
        try:
            recorder.open()
            recorder.begin()
            await asyncio.sleep(0.4)
            captured = recorder.finish()
            assert captured.startswith(b"RIFF") and len(captured) > 44
            del captured
            record("real_microphone_capture_ram_only")
        finally:
            recorder.close()
        trigger = KeyboardTrigger(
            config.trigger,
            config.execution,
            lambda: None,
            lambda: None,
            lambda: None,
            lambda: None,
        )
        trigger.open()
        trigger.close()
        record("real_global_keyboard_hook_opens_and_closes")

        async with httpx.AsyncClient(trust_env=False) as unauthenticated:
            response = await unauthenticated.get(config.model.endpoint + "/props")
            assert response.status_code == 401, response.status_code
        record("inference_metadata_requires_api_key")
        process = psutil.Process(state["pid"])
        report["server_rss_mib"] = round(process.memory_info().rss / 1024**2, 1)
        report["template"] = (await backend.probe())["template_sha256"]
    finally:
        if pump:
            pump.cancel()
            await asyncio.gather(pump, return_exceptions=True)
        if player:
            player.close()
        current = desktop._speakers()
        if current.id == original_device.id:
            current.EndpointVolume.SetMasterVolumeLevelScalar(original_level, None)
        gui.destroy()
        desktop.user32.SetForegroundWindow(original_foreground)
        await backend.close()
    report["passed"] = True
    return report


if __name__ == "__main__":
    cfg = load_config(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    result = asyncio.run(validate(cfg, interactive="--interactive" in sys.argv[2:]))
    output = AUDIO / "report.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=True))
