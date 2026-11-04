"""Opt-in real, read-only checks. Simulations cannot establish Windows support."""

import os
import subprocess
import sys

import pytest

pytestmark = [
    pytest.mark.windows,
    pytest.mark.skipif(
        sys.platform != "win32" or os.environ.get("COMPUTERFLOW_WINDOWS_TESTS") != "1",
        reason="Requires an interactive Windows desktop and explicit opt-in",
    ),
]


async def test_real_windows_snapshot_has_stable_native_window_ids():
    from computerflow.platform.windows import WindowsPlatform

    desktop = WindowsPlatform()
    context = await desktop.snapshot()
    assert context.windows
    assert len({w.id for w in context.windows}) == len(context.windows)
    assert context.foreground_id
    for window in context.windows:
        hwnd = int(window.id.split(":")[0], 16)
        current = desktop._window(hwnd)
        if current:
            assert current.pid == window.pid


async def test_real_core_audio_readback():
    from computerflow.platform.windows import WindowsPlatform

    desktop = WindowsPlatform()
    device = desktop._speakers()
    assert device.id
    assert 0 <= device.EndpointVolume.GetMasterVolumeLevelScalar() <= 1


async def test_real_smtc_session_query():
    from computerflow.platform.windows import WindowsPlatform

    manager = await WindowsPlatform._manager()
    sessions = list(manager.get_sessions())
    for session in sessions:
        assert isinstance(session.source_app_user_model_id, str)
        assert int(session.get_playback_info().playback_status) in range(6)


def test_fresh_process_can_open_microphone_before_first_desktop_snapshot():
    code = """
import asyncio
from computerflow.platform.windows import WindowsPlatform
from computerflow.audio.recorder import Recorder
from computerflow.core.config import TriggerConfig
desktop = WindowsPlatform()
recorder = Recorder(TriggerConfig(), lambda: None)
try:
    recorder.open()
    context = asyncio.run(desktop.snapshot())
    assert context.volume is not None, context.unavailable
    assert not any('Mediensteuerung nicht verfügbar' in message for message in context.unavailable)
finally:
    recorder.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stderr
