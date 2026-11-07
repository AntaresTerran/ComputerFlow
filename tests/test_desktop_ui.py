import asyncio
import time

import pytest

from computerflow.actuator.executor import Executor
from computerflow.app import Assistant
from computerflow.brain.desktop import bind_element, parse_desktop
from computerflow.core.config import Config, ExecutionConfig
from computerflow.core.contracts import (
    Act,
    Ask,
    FocusWindow,
    InspectUI,
    Steps,
    VisualClick,
    WriteText,
)
from computerflow.core.errors import ComputerFlowError
from computerflow.core.jobs import Job, State
from computerflow.platform.contracts import (
    AudioSession,
    Element,
    RegisteredApplication,
    ScreenSnapshot,
    UIContext,
    Window,
)
from computerflow.platform.geometry import Rect


@pytest.mark.parametrize(
    "prefix",
    [
        "Schreibe im aktivierten Fenster",
        "Schreibe im aktuellen Textfeld",
        "Ich verwende das aktuelle Textfeld und schreibe",
    ],
)
def test_spoken_text_scope_is_not_inserted(prefix, context):
    request = parse_desktop(f"{prefix} Grüße aus Köln.", context)
    assert isinstance(request, InspectUI) and request.operation == "write"
    assert request.value == "Grüße aus Köln."


def test_named_tab_and_stream_are_not_window_names(context):
    tab = parse_desktop("Wechsel in Firefox auf den Tab Home Assistant.", context)
    assert isinstance(tab, InspectUI)
    assert (tab.operation, tab.window, tab.value) == ("tab", "Firefox", "Home Assistant")
    stream = parse_desktop("Wechsle den Twitch-Stream auf Harmony.", context)
    assert isinstance(stream, InspectUI)
    assert (stream.operation, stream.source, stream.value) == ("stream", "Twitch", "Harmony")


@pytest.mark.parametrize(
    ("command", "title", "window"),
    [
        ("Wechsel auf den Home Assistant Tab von Firefox.", "Home Assistant", "Firefox"),
        ("Wechsle den Firefox-Tab auf Olamä.", "Olamä", "Firefox"),
        ("Wechsle auf die Termine-Registerkarte von Kalender.", "Termine", "Kalender"),
        ("Ich wechseln in Firefox Tab of Home Assistant.", "Home Assistant", "Firefox"),
        ("Ich wechsle auf den Tab Home Assistant.", "Home Assistant", None),
    ],
)
def test_spoken_tab_order_and_app_are_separated(context, command, title, window):
    request = parse_desktop(command, context)
    assert isinstance(request, InspectUI)
    assert (request.operation, request.value, request.window) == ("tab", title, window)


async def test_chat_draft_requires_the_named_window_and_focused_chat_input(context, desktop):
    request = parse_desktop("Schreibe in den Twitch-Chat Hi.", context)
    assert isinstance(request, InspectUI)
    assert (request.operation, request.source, request.value) == ("chat", "Twitch", "Hi.")
    assistant = Assistant(Config(), None, desktop, lambda _: None)
    decision, _ = await assistant._ui_decision(request, context, Job(5))
    assert isinstance(decision, Ask) and "Twitch" in decision.question

    window = context.windows[0].model_copy(update={"title": "Kanal – Twitch"})
    context = context.model_copy(update={"windows": (window,)})
    search = Element("search", (1, 2), "Textfeld", "Textfeld", Rect(0, 0, 80, 25), "write")
    chat = Element("chat", (1, 3), "Textfeld", "Textfeld", Rect(0, 30, 80, 55), "write", True)
    focused = search

    async def inspect(window_id, job):
        return UIContext("ui", window_id, time.monotonic(), (search, chat), focused.native_id)

    desktop.inspect_ui = inspect
    decision, _ = await assistant._ui_decision(request, context, Job(5))
    assert isinstance(decision, Ask)

    focused = chat
    job = Job(5)
    decision, bound = await assistant._ui_decision(request, context, job)
    assert isinstance(decision.action, WriteText)
    assert decision.action.text == "Hi." and decision.action.element_id == chat.id
    assert decision.action.in_chat and not decision.action.focus_first
    assistant.executor.validate(decision.action, bound, job)
    assert not desktop.calls


@pytest.mark.parametrize(
    ("command", "operation", "value", "scope"),
    [
        ("Ich wechsel den Twitch-Stream auf Jule.", "stream", "Jule", "Twitch"),
        ("Schreibe hell im Twitch-Chat.", "chat", "hell", "Twitch"),
        ("Dann klicke in Twitch auf Juli.", "activate", "Juli", "Twitch"),
        ("Klicke in Twitch auf Fail.", "activate", "Fail", "Twitch"),
    ],
)
def test_reported_commands_keep_action_scope_and_text(context, command, operation, value, scope):
    request = parse_desktop(command, context)
    assert (request.operation, request.value, request.window or request.source) == (
        operation,
        value,
        scope,
    )


async def test_any_apps_registered_name_is_bound_before_launch(context, desktop):
    app = RegisteredApplication(id="registered.app", name="Neues Werkzeug")

    async def registered(job):
        return (app,)

    desktop.registered_apps = registered
    assistant = Assistant(Config(), None, desktop, lambda _: None)
    steps = parse_desktop("Öffne Neues Werkzeug und schreibe Grüße.", context)
    assert isinstance(steps, Steps)
    request = parse_desktop(steps.commands[0], context)
    decision, bound = await assistant._open_application(request, context, Job(5))
    assert decision.action.registration_id == app.id and bound.launch_target == app
    assert assistant.executor.needs_confirmation(decision.action, bound)


@pytest.mark.parametrize(
    ("command", "label"),
    [
        ("Wechsle in Anderes Programm auf den Tab Projekte", "sichtbare Registerkarte „Projekte“"),
        (
            "Wechsle den Twitch-Stream auf Harmony",
            "sichtbares Klickziel für den Stream „Harmony“ auf „Twitch“",
        ),
    ],
)
async def test_generic_target_uses_visible_window_and_image_if_no_accessibility_match(
    context, desktop, command, label
):
    window = Window(
        id=context.foreground_id,
        title="Workspace – Twitch" if "Stream" in command else "Workspace",
        pid=1,
        application="Anderes Programm",
        process_name="arbitrary.exe",
    )
    context = context.model_copy(update={"windows": (window,)})
    request = parse_desktop(command, context)
    observed = []
    rect = Rect(0, 0, 300, 200)
    screen = ScreenSnapshot(
        "image", window.id, "monitor", rect, rect, (300, 200), (10, 10), time.monotonic(), b"png"
    )

    class Vision:
        async def locate(self, label, snapshot, job):
            observed.append((label, snapshot.id))
            return (300, 200)

    def capture(window_id, *, at_cursor, ui):
        assert window_id == window.id and not at_cursor
        return screen

    desktop.capture = capture
    assistant = Assistant(Config(), Vision(), desktop, lambda _: None)
    decision, bound = await assistant._ui_decision(request, context, Job(5))
    assert observed == [(label, screen.id)]
    assert isinstance(decision.action, VisualClick)
    assert assistant.executor.needs_confirmation(decision.action, bound)
    assert not desktop.calls


async def test_stream_search_finds_tab_in_any_application(context, desktop):
    window = Window(
        id="other",
        title="Workspace",
        pid=2,
        application="Anderes Programm",
        process_name="arbitrary.exe",
    )
    context = context.model_copy(update={"windows": (*context.windows, window)})
    tab = Element("tab", (1, 2), "Harmony – Twitch", "Registerkarte", Rect(0, 0, 120, 25), "select")

    async def inspect(window_id, job):
        elements = (tab,) if window_id == window.id else ()
        return UIContext("ui", window_id, time.monotonic(), elements, None)

    desktop.inspect_tabs = inspect
    assistant = Assistant(Config(), None, desktop, lambda _: None)
    request = parse_desktop("Wechsle den Twitch-Stream auf Harmony", context)
    decision, _ = await assistant._ui_decision(request, context, Job(5))
    focus, followup = decision.commands
    assert focus.action.window_id == followup.window_id == window.id
    assert not desktop.calls


async def test_tab_search_ignores_a_second_app_window_without_tabs(context, desktop):
    main = Window(id="main", title="Werkstatt", pid=2, application="Werkzeug")
    auxiliary = Window(id="aux", title="Optionen", pid=2, application="Werkzeug")
    context = context.model_copy(update={"windows": (*context.windows, main, auxiliary)})
    tab = Element("tab", (1, 2), "Übersicht", "Registerkarte", Rect(0, 0, 80, 25), "select")

    async def inspect(window_id, job):
        return UIContext("ui", window_id, time.monotonic(), (tab,) if window_id == main.id else ())

    desktop.inspect_tabs = inspect
    assistant = Assistant(Config(), None, desktop, lambda _: None)
    request = parse_desktop("Wechsle den Werkzeug-Tab auf Berichte", context)
    decision, _ = await assistant._ui_decision(request, context, Job(5))
    focus, followup = decision.commands
    assert focus.action.window_id == followup.window_id == main.id
    assert followup.value == "Berichte"
    assert not desktop.calls


@pytest.mark.parametrize("operation", ["activate", "stream"])
async def test_scoped_command_resolves_service_tab_before_visible_target(
    context, desktop, operation
):
    active = context.windows[0].model_copy(update={"title": "Übersicht"})
    context = context.model_copy(update={"windows": (active, *context.windows[1:])})
    tab = Element(
        "tab", (1, 2), "Start – Videodienst", "Registerkarte", Rect(0, 0, 80, 25), "select"
    )

    async def inspect(window_id, job):
        return UIContext(
            "ui", window_id, time.monotonic(), (tab,) if window_id == active.id else ()
        )

    desktop.inspect_tabs = inspect
    assistant = Assistant(Config(), None, desktop, lambda _: None)
    command = (
        "Klicke in Videodienst auf Juli"
        if operation == "activate"
        else ("Ich wechsel den Videodienst-Stream auf Juli")
    )
    request = parse_desktop(command, context)
    decision, bound = await assistant._ui_decision(request, context, Job(5))
    select, followup = decision.commands
    assert select.action.type == "ui_element" and select.action.element_id == tab.id
    assert followup.window_id == active.id and followup.value == "Juli"
    assistant.executor.validate(select.action, bound, Job(5))
    assert not desktop.calls


def test_unique_edit_can_receive_focus_but_password_and_incomplete_context_cannot(context):
    edit = Element("doc", (1, 2), "Dokument", "Dokument", Rect(0, 0, 60, 20), "write")
    request = InspectUI(kind="inspect_ui", operation="write", value="Grüße")
    ui = UIContext("ui", context.foreground_id, time.monotonic(), (edit,), (1, 3))
    assert bind_element(request, context.model_copy(update={"ui": ui})).action.focus_first
    for unsafe in (
        UIContext(ui.id, ui.window_id, ui.captured_at, ui.elements, ui.focus, protected_focus=True),
        UIContext(ui.id, ui.window_id, ui.captured_at, ui.elements, ui.focus, complete=False),
    ):
        assert isinstance(bind_element(request, context.model_copy(update={"ui": unsafe})), Ask)


def test_monitor_crop_maps_normalized_image_to_negative_physical_coordinates():
    monitor = Rect(-2560, -150, 0, 1290)
    crop = monitor.intersect(Rect(-600, -25, 380, 500))
    assert crop.point(0, 0) == (-600, -25)
    assert crop.point(1000, 1000) == (-1, 499)
    assert crop.point(*crop.normalized(-400, 120)) == (-400, 120)
    assert not crop.contains(0, 300)


def test_volume_resolves_relative_app_and_rejects_duplicate_sessions(context):
    app = AudioSession(id="session", app="Player", level=48)
    context = context.model_copy(update={"audio_sessions": (app,)})
    result = parse_desktop("Senke die Lautstärke von Player um dreizehn Prozent", context)
    assert result.action.session_id == app.id
    assert result.action.level == 35
    assert (
        parse_desktop("Setze die Systemlautstärke auf zweiunddreißig Prozent", context).action.level
        == 32
    )
    context = context.model_copy(
        update={"audio_sessions": (app, app.model_copy(update={"id": "another"}))}
    )
    assert isinstance(parse_desktop("Setze die Lautstärke von Player auf 30 Prozent", context), Ask)


def test_text_is_literal_and_uses_current_edit_focus(context, desktop):
    text = "Grüße 世界 🐈 und dann klicke auf Senden"
    request = parse_desktop(f"Schreibe „{text}“", context)
    assert isinstance(request, InspectUI) and request.value == text
    edit = Element("edit", (1, 2), "Textfeld", "Textfeld", Rect(0, 0, 60, 20), "write")
    context = context.model_copy(
        update={
            "ui": UIContext("ui", context.foreground_id, time.monotonic(), (edit,), edit.native_id)
        }
    )
    decision = bind_element(request, context)
    assert isinstance(decision, Act) and decision.action.text == text
    executor = Executor(desktop, ExecutionConfig())
    executor.validate(decision.action, context, Job(5))
    context = context.model_copy(
        update={"ui": UIContext("ui", context.foreground_id, time.monotonic(), (edit,), (3, 4))}
    )
    with pytest.raises(ComputerFlowError, match="Eingabefokus"):
        executor.validate(decision.action, context, Job(5))


async def test_visual_click_is_bound_to_exact_capture_and_approval(context, desktop):
    rect = Rect(-300, 20, -10, 170)
    screen = ScreenSnapshot(
        "screen-a",
        context.foreground_id,
        "left",
        rect,
        rect,
        (290, 150),
        (-60, 70),
        time.monotonic(),
        b"sample",
    )
    context = context.model_copy(update={"screen": screen})
    executor = Executor(desktop, ExecutionConfig())
    job = Job(10)
    action = VisualClick(
        type="visual_click",
        context_id=context.id,
        window_id=context.foreground_id,
        snapshot_id=screen.id,
        x=500,
        y=500,
        label="Testziel",
    )
    with pytest.raises(ComputerFlowError, match="Freigabe"):
        await executor.execute(action, context, job)
    confirmation = executor.request_confirmation(action, context, job)
    with pytest.raises(ComputerFlowError, match="Bildschirmaufnahme"):
        await executor.execute(
            action.model_copy(update={"snapshot_id": "wrong"}), context, job, confirmation
        )
    assert not desktop.calls


@pytest.mark.parametrize("native_focus_changes", [True, False])
async def test_sequence_checks_focus_before_planning_next_step(desktop, native_focus_changes):
    observed = []
    original = desktop.execute

    class Backend:
        async def plan(self, command, context, job, clarification):
            observed.append((command, context.foreground_id))
            explicit = parse_desktop(command, context)
            if explicit:
                return explicit
            return Act(
                kind="act",
                action=FocusWindow(type="focus_window", context_id=context.id, window_id="20:2"),
            )

    async def execute(action, context, job):
        result = await original(action, context, job)
        if isinstance(action, FocusWindow) and native_focus_changes:
            desktop.context = desktop.context.model_copy(
                update={"foreground_id": "20:2", "id": "fresh"}
            )
        await asyncio.sleep(0)
        return result

    desktop.execute = execute
    assistant = Assistant(Config(), Backend(), desktop, lambda _: None)
    result = await assistant.run(
        "Wechsle zum Browser und setze die Systemlautstärke auf 20 Prozent"
    )
    if native_focus_changes:
        assert result.state == State.DONE and result.executed == ("focus_window", "set_volume")
        assert observed[-1][1] == "20:2" and desktop.calls[-1].context_id == "fresh"
    else:
        assert result.state == State.FAILED and result.executed == ("focus_window",)
        assert len(observed) == 2
