import json

import pytest

from computerflow.core.contracts import Act, parse_decision


def test_valid_action():
    decision = parse_decision(
        json.dumps(
            {
                "kind": "act",
                "action": {
                    "type": "set_volume",
                    "context_id": "ctx",
                    "device_id": "d",
                    "level": 35,
                },
            }
        )
    )
    assert isinstance(decision, Act)
    assert decision.action.level == 35


@pytest.mark.parametrize(
    "action",
    [
        {"type": "shell", "command": "echo unsafe"},
        {"type": "hotkey", "keys": ["win", "r"]},
        {"type": "type_text", "text": "arbitrary"},
        {"type": "open_url", "url": "file:///secret"},
        {"type": "set_volume", "context_id": "c", "device_id": "d", "level": -1},
        {"type": "set_volume", "context_id": "c", "device_id": "d", "level": 101},
        {"type": "set_volume", "context_id": "c", "device_id": "d", "level": True},
        {"type": "set_volume", "context_id": "c", "device_id": "d", "level": "50"},
        {"type": "set_volume", "context_id": "c", "device_id": "d", "level": 50.5},
        {"type": "focus_window", "context_id": "c", "window_id": "w", "confirmed": True},
        {"type": "media_control", "context_id": "c", "session_id": "s", "operation": "toggle"},
        {"type": "focus_window", "window_id": "w"},
    ],
)
def test_unsafe_unknown_incomplete_actions_rejected(action):
    with pytest.raises(ValueError):
        parse_decision(json.dumps({"kind": "act", "action": action}))


@pytest.mark.parametrize(
    "content",
    [
        '{"kind":"stop","kind":"answer","message":"x"}',
        '{"kind":"act","action":{"type":"set_volume","context_id":"c",'
        '"device_id":"d","level":30,"level":100}}',
        '```json\n{"kind":"stop"}\n```',
        '{"kind":"stop"} trailing',
        '{"kind":"stop", "permission": true}',
        '{"kind":"ask","question":""}',
        '{"kind":"act"',
        "[]",
    ],
)
def test_ambiguous_non_json_and_extra_fields_rejected(content):
    with pytest.raises(ValueError):
        parse_decision(content)
