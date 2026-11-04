import pytest

from computerflow.brain.grounding import INTENT_ADAPTER, ground
from computerflow.core.contracts import Act, Ask
from computerflow.platform.contracts import Window


def intent(action):
    return INTENT_ADAPTER.validate_python({"kind": "act", "action": action})


def test_model_names_are_bound_to_current_window_and_context(context):
    decision = ground(
        intent({"type": "focus_window", "target": "Browser"}), context, "Wechsle zum Browser"
    )
    assert isinstance(decision, Act)
    assert decision.action.window_id == "20:2"
    assert decision.action.context_id == context.id


def test_split_german_asr_compounds_match_without_guessing(context):
    context = context.model_copy(
        update={"windows": (Window(id="test", title="ComputerFlow Testfenster Alpha", pid=1),)}
    )
    command = "Wechsle zum Computer Flow Test Fenster Alpha."
    decision = ground(
        intent({"type": "focus_window", "target": "Computer Flow Test Fenster Alpha"}),
        context,
        command,
    )
    assert isinstance(decision, Act)
    assert decision.action.window_id == "test"


def test_ambiguous_names_always_ask_even_if_model_decides_to_act(context):
    context = context.model_copy(
        update={
            "windows": (
                Window(id="a", title="Testfenster Alpha", pid=1),
                Window(id="b", title="Testfenster Beta", pid=1),
            )
        }
    )
    decision = ground(
        intent({"type": "focus_window", "target": "Testfenster"}),
        context,
        "Wechsle zum Testfenster",
    )
    assert isinstance(decision, Ask)


def test_model_cannot_add_unrequested_specificity_to_ambiguous_target(context):
    context = context.model_copy(
        update={
            "windows": (
                Window(id="a", title="Testfenster Alpha", pid=1),
                Window(id="b", title="Testfenster Beta", pid=1),
            )
        }
    )
    decision = ground(
        intent({"type": "focus_window", "target": "Testfenster Alpha"}),
        context,
        "Wechsle zum Testfenster",
    )
    assert isinstance(decision, Ask)


def test_missing_window_is_a_question_not_an_invented_id(context):
    decision = ground(
        intent({"type": "focus_window", "target": "Missing"}), context, "Wechsle zu Missing"
    )
    assert isinstance(decision, Ask)


def test_multiple_playback_sources_require_a_target(context):
    context = context.model_copy(
        update={
            "media_sessions": (
                context.media_sessions[0],
                context.media_sessions[0].model_copy(update={"id": "other", "app": "other"}),
            )
        }
    )
    decision = ground(
        intent({"type": "media_control", "operation": "pause", "target": None}), context, "Pausiere"
    )
    assert isinstance(decision, Ask)


def test_model_cannot_provide_internal_ids_or_confirmation():
    with pytest.raises(ValueError):
        intent({"type": "focus_window", "target": "x", "window_id": "injected", "confirmed": True})
