import json

import httpx
import pytest

from computerflow.brain.llama_cpp import LlamaCppBackend
from computerflow.core.config import ModelConfig
from computerflow.core.errors import BackendError
from computerflow.core.jobs import Job


def recognizer(text, finish="stop"):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": finish,
                        "message": {"content": text},
                    }
                ]
            },
        )

    client = httpx.AsyncClient(base_url="http://127.0.0.1", transport=httpx.MockTransport(respond))
    return LlamaCppBackend(ModelConfig(), client), requests


@pytest.mark.parametrize("word", ["abbrechen", "Abbrechen.", "Computer, stopp!", "Stopp"])
async def test_recognized_stop_never_enters_action_planning(word, context):
    backend, requests = recognizer(word)
    result = await backend.plan(b"synthetic-wav", context, Job(5))
    assert result.kind == "stop"
    assert len(requests) == 1
    assert requests[0]["messages"][0]["content"] == "Perform ASR in German."
    assert "response_format" not in requests[0]
    await backend.close()


@pytest.mark.parametrize("word", ["Abbrechen.", "stopp", "Computer, abbrechen!"])
async def test_explicit_text_stop_never_contacts_model(word, context):
    backend, requests = recognizer("unused")
    assert (await backend.plan(word, context, Job(5))).kind == "stop"
    assert not requests
    await backend.close()


async def test_german_compound_percentage_regression():
    backend, _ = recognizer("Setze die Systemlautstärke auf 9 und 30 Prozent.")
    assert await backend.transcribe(b"synthetic-wav", Job(5)) == (
        "Setze die Systemlautstärke auf 39 Prozent."
    )
    await backend.close()


@pytest.mark.parametrize("text,finish", [("", "stop"), ("partial", "length"), (None, "stop")])
async def test_empty_truncated_or_nontext_asr_is_not_planned(text, finish, context):
    backend, requests = recognizer(text, finish)
    with pytest.raises(BackendError, match="Spracherkennung"):
        await backend.plan(b"synthetic-wav", context, Job(5))
    assert len(requests) == 1
    await backend.close()


async def test_app_vocabulary_is_separate_from_audio_and_not_from_window_titles(context):
    from computerflow.platform.contracts import Window

    context = context.model_copy(
        update={
            "windows": (
                Window(
                    id="mail",
                    pid=1,
                    title="private-mail-subject",
                    application="Thunderbird",
                    process_name="thunderbird.exe",
                ),
            )
        }
    )
    backend, requests = recognizer("Abbrechen.")
    result = await backend.plan(b"synthetic-wav", context, Job(5))
    assert result.kind == "stop"
    request = requests[0]
    assert "Thunderbird" in request["messages"][0]["content"]
    assert "private-mail-subject" not in json.dumps(request)
    assert len(request["messages"][1]["content"]) == 1
    assert request["messages"][1]["content"][0]["type"] == "input_audio"
    await backend.close()
