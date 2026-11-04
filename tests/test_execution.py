import asyncio
import time
from dataclasses import replace

import pytest

from computerflow.actuator.executor import Executor
from computerflow.core.config import ExecutionConfig
from computerflow.core.contracts import FocusWindow, MediaControl, SetVolume
from computerflow.core.errors import Cancelled, ComputerFlowError
from computerflow.core.jobs import Job, State


def volume(context, level=30):
    return SetVolume(type="set_volume", context_id=context.id, device_id="speakers", level=level)


async def test_known_action_executes_once_and_verifies(context, desktop):
    job = Job(5)
    result = await Executor(desktop, ExecutionConfig()).execute(volume(context), context, job)
    assert result.verified
    assert len(desktop.calls) == 1
    assert job.state == State.DONE


async def test_unverified_action_never_retried(context, desktop):
    desktop.verified = False
    job = Job(5)
    result = await Executor(desktop, ExecutionConfig()).execute(volume(context), context, job)
    assert not result.verified
    assert len(desktop.calls) == 1
    assert job.state == State.FAILED


@pytest.mark.parametrize("mode", ["wrong_context", "stale", "future", "wrong_device", "cancelled"])
async def test_invalid_context_or_cancelled_job_never_executes(mode, context, desktop):
    action = volume(context)
    job = Job(5)
    if mode == "wrong_context":
        action = action.model_copy(update={"context_id": "other"})
    elif mode == "stale":
        context = context.model_copy(update={"captured_at": time.monotonic() - 100})
    elif mode == "future":
        context = context.model_copy(update={"captured_at": time.monotonic() + 100})
    elif mode == "wrong_device":
        action = action.model_copy(update={"device_id": "other"})
    else:
        job.cancel()
    with pytest.raises(ComputerFlowError):
        await Executor(desktop, ExecutionConfig()).execute(action, context, job)
    assert not desktop.calls


async def test_unknown_window_rejected(context, desktop):
    action = FocusWindow(type="focus_window", context_id=context.id, window_id="not-present")
    with pytest.raises(ComputerFlowError):
        await Executor(desktop, ExecutionConfig()).execute(action, context, Job(5))
    assert not desktop.calls


async def test_media_capabilities_enforced(context, desktop):
    context = context.model_copy(
        update={
            "media_sessions": (context.media_sessions[0].model_copy(update={"can_pause": False}),),
        }
    )
    action = MediaControl(
        type="media_control",
        context_id=context.id,
        session_id="music",
        operation="pause",
    )
    with pytest.raises(ComputerFlowError):
        await Executor(desktop, ExecutionConfig()).execute(action, context, Job(5))
    assert not desktop.calls


@pytest.mark.parametrize("mutation", ["action", "job", "expiry", "token", "missing"])
async def test_confirmation_is_bound_and_expires(mutation, context, desktop):
    executor = Executor(desktop, ExecutionConfig(practice_mode=True))
    job = Job(5)
    action = volume(context)
    approval = executor.request_confirmation(action, context, job)
    if mutation == "action":
        action = volume(context, 80)
    elif mutation == "job":
        job = Job(5)
    elif mutation == "expiry":
        approval = replace(approval, expires_at=time.monotonic() - 1)
        executor._pending = approval
    elif mutation == "token":
        approval = replace(approval, token="forged")
    else:
        approval = None
    with pytest.raises(ComputerFlowError):
        await executor.execute(action, context, job, approval)
    assert not desktop.calls


async def test_confirmation_is_single_use(context, desktop):
    executor = Executor(desktop, ExecutionConfig(practice_mode=True))
    job = Job(5)
    action = volume(context)
    approval = executor.request_confirmation(action, context, job)
    await executor.execute(action, context, job, approval)
    with pytest.raises(ComputerFlowError):
        await executor.execute(action, context, job, approval)
    assert len(desktop.calls) == 1


async def test_job_discards_response_even_if_backend_ignores_cancellation():
    job = Job(5)

    async def late():
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            return "late"

    task = asyncio.create_task(job.guard(late()))
    await asyncio.sleep(0)
    job.cancel()
    with pytest.raises(Cancelled):
        await task


async def test_deadline_cancels_pending_work():
    job = Job(0.01)
    with pytest.raises(Cancelled):
        await job.guard(asyncio.sleep(5))
    assert job.state == State.CANCELLED
