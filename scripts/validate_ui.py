"""Exercise the Windows adapter on a temporary, isolated WinForms test surface."""

import asyncio
import json
import os
import subprocess
from pathlib import Path

from computerflow.app import Assistant
from computerflow.brain.llama_cpp import LlamaCppBackend
from computerflow.core.config import load_config
from computerflow.core.errors import PlatformError
from computerflow.core.jobs import Job, State
from computerflow.platform.windows import WindowsPlatform
from computerflow.runtime.manager import ManagedRuntime

ROOT = Path(__file__).resolve().parents[1]


async def controlled(assistant, command, approve=lambda pending: None):
    task = asyncio.create_task(assistant.run(command))
    try:
        while not task.done() and assistant.pending_confirmation is None:  # noqa: ASYNC110
            await asyncio.sleep(0.025)
        if assistant.pending_confirmation:
            approve(json.loads(assistant.pending_confirmation.action_json))
            assistant.confirm()
        result = await task
        print(command, result.state, result.message, flush=True)
        assert result.state == State.DONE
        return result
    finally:
        if not task.done():
            assistant.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def validate(desktop, config, hwnd, canvas):
    assert desktop.user32.GetForegroundWindow() == hwnd, "Testfenster ist nicht im Vordergrund"
    context = await desktop.snapshot()
    expected = context.foreground_id
    original_vision = desktop.ui.config
    desktop.ui.config = original_vision.model_copy(
        update={"excluded_titles": ("ComputerFlow 003 UI Test",)}
    )
    try:
        desktop.capture(expected)
    except PlatformError as error:
        assert "Ausschluss" in str(error)
    else:
        raise AssertionError("Protected fixture was captured")
    finally:
        desktop.ui.config = original_vision
    ui = await desktop.inspect_ui(expected, Job(5))
    print([(e.label, e.operation) for e in ui.elements], flush=True)
    assert any(e.operation == "write" and e.native_id == ui.focus for e in ui.elements)
    assert any(e.label == "Test Option" and e.operation == "toggle" for e in ui.elements)
    screen = desktop.capture(expected, ui=ui)
    assert screen.png.startswith(b"\x89PNG") and screen.marks
    print(
        f"Captured allowed fixture area {screen.image_size}; {len(screen.marks)} marks; "
        f"{len(desktop.ui.screen.monitors())} monitor(s)"
    )
    managed = ManagedRuntime(config)
    state = managed.connection()
    assert state is not None, "Start-ComputerFlow.ps1 -Doctor zuerst ausführen"
    backend = LlamaCppBackend(config.model, api_key=state["api_key"])
    assistant = Assistant(config, backend, desktop, print)
    try:
        commands = (
            "Schreibe Grüße, 世界 und 🐈.",
            "Klicke auf Test Option",
            "Klicke auf Test Button",
        )
        for command in commands:
            await controlled(assistant, command)
        app = next((s for s in context.audio_sessions if "uifixture" in s.app.casefold()), None)
        assert app is not None, "Stumme Testwiedergabe hat keine eigene Windows-Sitzung"
        try:
            result = await assistant.run(f"Setze die Lautstärke von {app.app} auf 23 Prozent")
            assert result.state == State.DONE and "23 %" in result.message
        finally:
            restored = await assistant.run(
                f"Setze die Lautstärke von {app.app} auf {app.level} Prozent"
            )
            assert restored.state == State.DONE
        point = await backend.locate("VISUAL TARGET", screen, Job(15))
        print(f"Real model visual target proposal: {point}", flush=True)
        canvas_rect = desktop.ui.screen.rect(canvas)
        assert point is not None and canvas_rect.contains(*screen.crop.point(*point))
        original_cursor = desktop.ui.screen.cursor()
        center = (
            (canvas_rect.left + canvas_rect.right) // 2,
            (canvas_rect.top + canvas_rect.bottom) // 2,
        )

        def approve_fixture_click(action):
            assert action["window_id"] == expected
            assert canvas_rect.contains(*screen.crop.point(action["x"], action["y"]))

        try:
            await controlled(assistant, "Klicke auf VISUAL TARGET", approve_fixture_click)
            assert desktop.user32.SetCursorPos(*center)
            await controlled(assistant, "Klick hier", approve_fixture_click)
            original_monitor = screen.monitor_id
            for monitor_id, bounds in desktop.ui.screen.monitors():
                if monitor_id == original_monitor or min(bounds.width, bounds.height) < 300:
                    continue
                # Move only this test process's window to a second physical monitor.
                assert desktop.user32.SetWindowPos(
                    hwnd, None, bounds.left + 20, bounds.top + 20, 0, 0, 0x15
                )
                await asyncio.sleep(0.15)
                canvas_rect = desktop.ui.screen.rect(canvas)
                center = (
                    (canvas_rect.left + canvas_rect.right) // 2,
                    (canvas_rect.top + canvas_rect.bottom) // 2,
                )
                assert desktop.user32.SetCursorPos(*center)
                screen = desktop.capture(expected, at_cursor=True)
                assert screen.monitor_id == monitor_id and screen.crop.contains(*center)
                print(f"Verifying cursor click on physical monitor at {bounds.left}, {bounds.top}")
                await controlled(assistant, "Klick hier", approve_fixture_click)
        finally:
            if canvas_rect.contains(*desktop.ui.screen.cursor()):
                desktop.user32.SetCursorPos(*original_cursor)
        result = await assistant.run("Wechsle zu ComputerFlow 003 Secondary und schreibe Grüße")
        print(result.state, result.message, result.executed, flush=True)
        assert result.state == State.DONE and result.executed[-1] == "write_text"
        assert result.executed[0] in {"restore_window", "focus_window"}
        result = await controlled(assistant, "Wechsle auf den Tab Pruefseite")
        assert result.executed == ("ui_element",)
    finally:
        await backend.close()


async def main():
    config = load_config(ROOT / "config.yaml")
    await asyncio.to_thread(ManagedRuntime(config).start)
    desktop = WindowsPlatform(config.vision)
    scratch = ROOT / ".computerflow/validation"
    scratch.mkdir(parents=True, exist_ok=True)
    executable = scratch / "ComputerFlow.UiFixture.exe"
    csc = Path(os.environ["SystemRoot"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    compiler = await asyncio.create_subprocess_exec(
        str(csc),
        "/nologo",
        "/target:exe",
        f"/out:{executable}",
        str(ROOT / "scripts/UiFixture.cs"),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert await compiler.wait() == 0
    process = await asyncio.create_subprocess_exec(
        str(executable),
        str(os.getpid()),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        line = await asyncio.wait_for(process.stdout.readline(), 12)
        hwnd, canvas = (int(part) for part in line.split())
        await validate(desktop, config, hwnd, canvas)
    finally:
        if process.returncode is None:
            process.terminate()
        await process.communicate()


if __name__ == "__main__":
    asyncio.run(main())
