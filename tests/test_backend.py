import asyncio
import base64
import io
import json
import time

import httpx
import pytest

from computerflow.app import Assistant
from computerflow.audio.recorder import pcm_to_wav
from computerflow.brain.llama_cpp import LlamaCppBackend
from computerflow.core.config import Config, ModelConfig
from computerflow.core.contracts import Ask, InspectUI
from computerflow.core.errors import BackendError
from computerflow.core.jobs import Job, State
from computerflow.platform.contracts import ScreenSnapshot, Window
from computerflow.platform.geometry import Rect


def backend(handler, repairs=1):
    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:8080", transport=httpx.MockTransport(handler)
    )
    return LlamaCppBackend(ModelConfig(max_response_repairs=repairs), client)


def completion(content, finish="stop"):
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": finish,
                    "message": {"content": content},
                }
            ]
        },
    )


async def test_audio_to_http_to_validated_execution_simulation(context, desktop):
    requests = []
    wav = pcm_to_wav(b"\x00\x00" * 8000)

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if payload["messages"][0]["content"] == "Perform ASR in German.":
            return completion("Die Systemlautstärke soll bei 25 Prozent liegen.")
        return completion(
            json.dumps(
                {
                    "kind": "act",
                    "action": {
                        "type": "set_volume",
                        "level": 25,
                    },
                }
            )
        )

    model = backend(respond)
    try:
        entry = await Assistant(Config(), model, desktop, lambda _: None).run(wav)
    finally:
        await model.close()
    assert entry.state == State.DONE
    assert entry.executed == ("set_volume",)
    assert len(desktop.calls) == 1
    audio = requests[0]["messages"][1]["content"][0]["input_audio"]
    assert base64.b64decode(audio["data"]) == wav
    assert len(requests) == 2
    payload = requests[1]
    assert payload["response_format"]["schema"]
    assert payload["cache_prompt"] is False
    assert payload["stream"] is False
    assert payload["reasoning_format"] == "auto"


async def test_invalid_response_repaired_at_most_once(context):
    calls = []

    def respond(request):
        calls.append(request)
        return completion('{"kind":"act","action":{"type":"shell"}}')

    model = backend(respond)
    with pytest.raises(BackendError, match="verworfen"):
        await model.plan("test", context, Job(5))
    assert len(calls) == 2
    await model.close()


async def test_old_window_question_cannot_authorize_new_garbled_request(context, desktop):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return completion('{"kind":"act","action":{"type":"focus_window","target":"Browser"}}')

    model = backend(respond)
    assistant = Assistant(Config(), model, desktop, lambda _: None)
    try:
        first = await assistant.run("Wechsle zu Home Assistant")
        assert first.state == State.WAITING and "Home Assistant" in first.message
        second = await assistant.run("Excellent Browser Stream of July.")
        assert second.state == State.WAITING and "Home Assistant" not in second.message
        assert not desktop.calls
        assert len(requests) == 1 and "previous_question" not in str(requests[0])
    finally:
        await model.close()


async def test_short_app_and_tab_reply_requires_an_observed_tab(context):
    window = Window(id="app", pid=1, title="Overview", application="Werkzeug App")
    context = context.model_copy(update={"windows": (window,)})
    model = backend(lambda _: pytest.fail("short tab target should be resolved locally"))
    try:
        request = await model.plan("Werkzeug App Home Assistant", context, Job(5))
        assert isinstance(request, InspectUI) and request.exact_tab
        assert (request.operation, request.window, request.value) == (
            "tab",
            "Werkzeug App",
            "Home Assistant",
        )
    finally:
        await model.close()


@pytest.mark.parametrize(
    ("action", "selects_tab"),
    [
        ({"type": "select_tab", "target": "Berichte", "window": "Kalender"}, True),
        ({"type": "select_tab", "target": "Unbenannt", "window": "Kalender"}, False),
        ({"type": "focus_window", "target": "Kalender"}, False),
    ],
)
async def test_model_tab_fallback_uses_spoken_names_and_cannot_focus_a_window(
    context, action, selects_tab
):
    model = backend(lambda _: completion(json.dumps({"kind": "act", "action": action})))
    try:
        decision = await model.plan("Wechsle zu Berichte, dem Tab in Kalender.", context, Job(5))
        if selects_tab:
            assert isinstance(decision, InspectUI)
            assert (decision.operation, decision.value, decision.window) == (
                "tab",
                "Berichte",
                "Kalender",
            )
        else:
            assert isinstance(decision, Ask)
    finally:
        await model.close()


@pytest.mark.parametrize(
    ("direction", "image_size", "point"),
    [("horizontal", (200, 20), (401, 180)), ("vertical", (40, 100), (180, 401))],
)
async def test_tab_vision_crops_to_the_detected_axis_and_maps_to_original(
    direction, image_size, point
):
    image = pytest.importorskip("PIL.Image")
    png = io.BytesIO()
    image.new("RGB", (200, 100)).save(png, format="PNG")
    bounds = Rect(-400, -60, 400, 340)
    screen = ScreenSnapshot(
        "s", "w", "m", bounds, bounds, (200, 100), (0, 0), time.monotonic(), png.getvalue()
    )
    requests = []

    def respond(request):
        parts = json.loads(request.content)["messages"][1]["content"]
        raw = base64.b64decode(parts[0]["image_url"]["url"].split(",", 1)[1])
        with image.open(io.BytesIO(raw)) as sent:
            requests.append(sent.size)
        if len(requests) == 1:
            return completion(
                json.dumps(
                    {"left": 100, "top": 100, "right": 300, "bottom": 300, "direction": direction}
                )
            )
        return completion('{"x":400,"y":400,"mark":null}')

    model = backend(respond)
    try:
        actual = await model.locate_tab("Berichte", screen, Job(5))
        assert actual == point
        assert requests == [(200, 100), image_size]
    finally:
        await model.close()


async def test_truncated_but_parseable_response_is_not_executed(context, desktop):
    model = backend(lambda _: completion('{"kind":"stop"}', "length"), repairs=0)
    entry = await Assistant(Config(), model, desktop, lambda _: None).run("test")
    assert entry.state == State.FAILED
    assert not desktop.calls
    await model.close()


@pytest.mark.parametrize("status", [301, 400, 500, 503])
async def test_http_errors_have_no_mock_fallback(status, context, desktop):
    model = backend(lambda _: httpx.Response(status, text="private-server-detail"))
    entry = await Assistant(Config(), model, desktop, lambda _: None).run("test")
    assert entry.state == State.FAILED
    assert not desktop.calls
    assert "private-server-detail" not in entry.message
    await model.close()


async def test_connection_failure_is_controlled(context):
    def fail(request):
        raise httpx.ConnectError("private", request=request)

    model = backend(fail)
    with pytest.raises(BackendError, match="nicht erreichbar"):
        await model.plan("test", context, Job(5))
    await model.close()


async def test_native_tool_output_is_normalized(context):
    response = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "computerflow_decision",
                                "arguments": '{"kind":"stop"}',
                            },
                        }
                    ],
                },
            }
        ]
    }
    model = backend(lambda _: httpx.Response(200, json=response))
    assert (await model.plan("beende den Auftrag bitte", context, Job(5))).kind == "stop"
    await model.close()


async def test_cancel_during_inference_prevents_execution(context, desktop):
    started = asyncio.Event()

    async def delayed(request):
        started.set()
        await asyncio.sleep(30)
        return completion("unreachable")

    model = backend(delayed)
    assistant = Assistant(Config(), model, desktop, lambda _: None)
    task = asyncio.create_task(assistant.run("test"))
    await started.wait()
    assistant.cancel()
    entry = await task
    assert entry.state == State.CANCELLED
    assert not desktop.calls
    await model.close()


async def test_server_probe_records_actual_template_and_build():
    def respond(request):
        values = {
            "/health": {"status": "ok"},
            "/props": {
                "chat_template": "official-template",
                "build_info": "test-build",
                "modalities": {"audio": True},
            },
            "/v1/models": {"data": [{"id": ModelConfig().model_id}]},
        }
        return httpx.Response(200, json=values[request.url.path])

    model = backend(respond)
    report = await model.probe()
    assert report["runtime_build"] == "test-build"
    assert len(report["template_sha256"]) == 64
    assert report["audio_input_reported"] is True
    assert report["model_revision_configured"] is None
    await model.close()
