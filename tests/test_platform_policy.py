"""Platform edge cases using explicit simulations, without native OS calls."""

import sys
from types import SimpleNamespace

import pytest

from computerflow.core.contracts import FocusWindow, SetVolume
from computerflow.core.errors import PlatformError
from computerflow.core.jobs import Job, State
from computerflow.platform.windows import WindowsPlatform


def adapter():
    # __init__ is intentionally bypassed: these are not Windows integration tests.
    return object.__new__(WindowsPlatform)


async def test_manual_focus_change_blocks_before_any_os_action(context):
    desktop = adapter()
    desktop.foreground_id = lambda: "changed"
    action = SetVolume(type="set_volume", context_id=context.id, device_id="speakers", level=30)
    with pytest.raises(PlatformError, match="geändert"):
        await desktop.execute(action, context, Job(5))


async def test_changed_volume_device_is_not_retargeted(context):
    desktop = adapter()
    desktop.foreground_id = lambda: context.foreground_id
    desktop._speakers = lambda: SimpleNamespace(id="new-speakers")
    action = SetVolume(type="set_volume", context_id=context.id, device_id="speakers", level=30)
    with pytest.raises(PlatformError, match="geändert"):
        await desktop.execute(action, context, Job(5))


async def test_sending_volume_event_is_not_itself_success(context):
    writes = []
    endpoint = SimpleNamespace(
        SetMasterVolumeLevelScalar=lambda value, _: writes.append(value),
        GetMasterVolumeLevelScalar=lambda: 0.8,
    )
    desktop = adapter()
    desktop.foreground_id = lambda: context.foreground_id
    desktop._speakers = lambda: SimpleNamespace(id="speakers", EndpointVolume=endpoint)
    action = SetVolume(type="set_volume", context_id=context.id, device_id="speakers", level=30)
    job = Job(5)
    result = await desktop.execute(action, context, job)
    assert result.verified is False
    assert writes == [0.3]
    assert job.executed == ["set_volume"]
    assert job.state == State.VERIFYING


async def test_window_title_change_blocks_focus(context):
    desktop = adapter()
    desktop.foreground_id = lambda: context.foreground_id
    desktop._window = lambda hwnd: context.windows[1].model_copy(update={"title": "different"})
    action = FocusWindow(type="focus_window", context_id=context.id, window_id="20:2")
    with pytest.raises(PlatformError, match="Fensteridentität"):
        await desktop.execute(action, context, Job(5))


def test_unsupported_platform_is_explicit():
    if sys.platform != "win32":
        with pytest.raises(PlatformError, match="nur auf Windows"):
            WindowsPlatform()
