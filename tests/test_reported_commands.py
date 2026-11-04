import json

import httpx
import pytest

from computerflow.brain.commands import parse_explicit_command
from computerflow.brain.grounding import ground
from computerflow.brain.llama_cpp import LlamaCppBackend
from computerflow.core.config import ModelConfig
from computerflow.core.contracts import Act, Ask
from computerflow.core.jobs import Job
from computerflow.platform.applications import application_info
from computerflow.platform.contracts import MediaSession, Window


@pytest.mark.parametrize("title", ["Posteingang", "Gesendet", "Entwürfe"])
def test_thunderbird_matches_application_identity_regardless_of_folder_title(context, title):
    context = context.model_copy(
        update={
            "windows": (
                Window(
                    id="mail",
                    pid=7,
                    title=title,
                    application="Thunderbird",
                    process_name="thunderbird.exe",
                ),
            )
        }
    )
    command = "Wechsle zu Thunderbird"
    result = ground(parse_explicit_command(command), context, command)
    assert isinstance(result, Act) and result.action.window_id == "mail"


def test_editor_matches_notepad_process_even_when_title_is_only_a_filename(context):
    info = application_info("notepad.exe")
    context = context.model_copy(
        update={
            "windows": (
                Window(
                    id="editor",
                    pid=8,
                    title="Notizen.txt",
                    application=info.name,
                    process_name=info.process_name,
                    app_aliases=info.aliases,
                ),
            )
        }
    )
    result = ground(parse_explicit_command("Wechsle zum Editor"), context, "Wechsle zum Editor")
    assert isinstance(result, Act) and result.action.window_id == "editor"


@pytest.mark.parametrize(
    "name, label", [("Steam", "Steam Client WebHelper"), ("Acme", "Acme Viewer")]
)
def test_unique_short_application_name_matches_native_product_metadata(context, name, label):
    window = Window(id="found", pid=9, title="Bibliothek", application=label)
    current = context.model_copy(update={"windows": (window,)})
    command = f"Wechsle zu {name}"
    intent = parse_explicit_command(command)
    result = ground(intent, current, command)
    assert isinstance(result, Act) and result.action.window_id == window.id

    second = Window(id="other", pid=9, title="Einstellungen", application=label)
    current = current.model_copy(update={"windows": (window, second)})
    assert isinstance(ground(intent, current, command), Ask)


def test_multiple_windows_from_same_application_are_not_chosen_arbitrarily(context):
    context = context.model_copy(
        update={
            "windows": tuple(
                Window(id=name, pid=9, title=name, application="Editor", process_name="notepad.exe")
                for name in ["a.txt", "b.txt"]
            )
        }
    )
    result = ground(parse_explicit_command("Wechsle zum Editor"), context, "Wechsle zum Editor")
    assert isinstance(result, Ask)


def test_chet_suggests_chatgpt_but_does_not_automatically_focus_it(context):
    context = context.model_copy(
        update={
            "windows": (
                Window(
                    id="chat",
                    pid=10,
                    title="ChatGPT",
                    application="ChatGPT",
                    process_name="ChatGPT.exe",
                ),
            )
        }
    )
    result = ground(parse_explicit_command("Wechsle zu Chet"), context, "Wechsle zu Chet")
    assert isinstance(result, Ask) and "ChatGPT" in result.question


@pytest.mark.parametrize(
    "command",
    [
        "Pausiere Spotify",
        "Spotify, Pause",
        "Spotify Pause",
        "Pausieres Spotify.",
        "Pausiere die Wiedergabe in Spotify",
        "Computer, Spotify, Pause!",
    ],
)
async def test_clear_spotify_pause_commands_cannot_be_misclassified_as_window_focus(
    context, command
):
    context = context.model_copy(
        update={
            "media_sessions": (
                MediaSession(
                    id="spotify",
                    app="SpotifyAB.SpotifyMusic!App",
                    app_aliases=("Spotify",),
                    status="playing",
                    can_pause=True,
                    can_play=False,
                ),
            )
        }
    )

    def unexpected_request(request):
        pytest.fail("Clear command must not depend on model intent classification")

    client = httpx.AsyncClient(
        base_url="http://127.0.0.1", transport=httpx.MockTransport(unexpected_request)
    )
    backend = LlamaCppBackend(ModelConfig(), client)
    try:
        result = await backend.plan(command, context, Job(5))
        assert isinstance(result, Act)
        assert result.action.type == "media_control" and result.action.operation == "pause"
        assert result.action.session_id == "spotify"
    finally:
        await backend.close()


@pytest.mark.parametrize(
    "action",
    [
        {"type": "focus_window", "target": "Hausier Spotify"},
        {"type": "media_control", "target": "Spotify", "operation": "play"},
        {"type": "set_volume", "level": 20},
    ],
)
async def test_unclear_hausier_cannot_trigger_an_unrequested_focus_or_play(context, action):
    def response(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps({"kind": "act", "action": action})},
                    }
                ]
            },
        )

    client = httpx.AsyncClient(base_url="http://127.0.0.1", transport=httpx.MockTransport(response))
    backend = LlamaCppBackend(ModelConfig(), client)
    try:
        assert isinstance(await backend.plan("Hausier Spotify", context, Job(5)), Ask)
    finally:
        await backend.close()


@pytest.mark.parametrize(
    "command", ["Pausiere Spotify nicht", "Spotify keine Pause", "Nicht Spotify pausieren"]
)
def test_negated_media_commands_do_not_enter_direct_execution(command):
    assert parse_explicit_command(command) is None


def test_application_resource_metadata_cannot_create_alias_for_unrelated_known_product():
    info = application_info("ChatGPT.exe", ("Codex", "Electron"))
    assert info.name == "ChatGPT" and "Codex" not in info.aliases and "Electron" not in info.aliases


def test_unknown_apps_use_product_metadata_and_executable_name():
    info = application_info("mailclient.exe", ("Acme Mail", "Electron"))
    assert (
        info.name == "Acme Mail" and "mailclient" in info.aliases and "Electron" not in info.aliases
    )
