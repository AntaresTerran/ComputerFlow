"""Allowlisted actions. No arbitrary key chords or shell actions."""

import json
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from computerflow.core.config import StrictModel

Reference = Annotated[str, Field(min_length=1, max_length=256)]


class FocusWindow(StrictModel):
    type: Literal["focus_window"]
    context_id: Reference
    window_id: Reference


class LaunchApplication(StrictModel):
    type: Literal["launch_application"]
    context_id: Reference
    registration_id: Reference


class SetVolume(StrictModel):
    type: Literal["set_volume"]
    context_id: Reference
    device_id: Reference
    level: int = Field(ge=0, le=100)


class MediaControl(StrictModel):
    type: Literal["media_control"]
    context_id: Reference
    session_id: Reference
    operation: Literal["play", "pause"]


class SetAppVolume(StrictModel):
    type: Literal["set_app_volume"]
    context_id: Reference
    session_id: Reference
    level: int = Field(ge=0, le=100)


class UIElementAction(StrictModel):
    type: Literal["ui_element"]
    context_id: Reference
    window_id: Reference
    ui_id: Reference
    element_id: Reference


class WriteText(StrictModel):
    type: Literal["write_text"]
    context_id: Reference
    window_id: Reference
    ui_id: Reference
    element_id: Reference
    text: str = Field(min_length=1, max_length=500)
    focus_first: bool = False
    in_chat: bool = False


class BrowserKey(StrictModel):
    type: Literal["browser_key"]
    context_id: Reference
    window_id: Reference
    key: Literal["address", "next_tab", "previous_tab", "back", "forward", "reload"]


class VisualClick(StrictModel):
    type: Literal["visual_click"]
    context_id: Reference
    window_id: Reference
    snapshot_id: Reference
    x: int = Field(ge=0, le=1000)
    y: int = Field(ge=0, le=1000)
    label: str = Field(min_length=1, max_length=150)
    at_cursor: bool = False


Action = Annotated[
    FocusWindow
    | LaunchApplication
    | SetVolume
    | MediaControl
    | SetAppVolume
    | UIElementAction
    | WriteText
    | BrowserKey
    | VisualClick,
    Field(discriminator="type"),
]
ACTION_ADAPTER = TypeAdapter(Action)


class Act(StrictModel):
    kind: Literal["act"]
    action: Action


class Ask(StrictModel):
    kind: Literal["ask"]
    question: str = Field(min_length=1, max_length=500)
    reply: Literal["window", "tab", "volume", "play", "pause"] | None = None


class Answer(StrictModel):
    kind: Literal["answer"]
    message: str = Field(min_length=1, max_length=500)


class Stop(StrictModel):
    kind: Literal["stop"]


class InspectUI(StrictModel):
    kind: Literal["inspect_ui"]
    operation: Literal["activate", "write", "chat", "cursor", "tab", "stream"]
    value: str = Field(min_length=1, max_length=500)
    window: str | None = Field(default=None, min_length=1, max_length=120)
    window_id: Reference | None = None
    source: str | None = Field(default=None, min_length=1, max_length=80)
    exact_tab: bool = False


class OpenApplication(StrictModel):
    kind: Literal["open_application"]
    name: str = Field(min_length=1, max_length=150)


class Steps(StrictModel):
    kind: Literal["steps"]
    commands: tuple[str | Act | InspectUI, ...] = Field(min_length=2, max_length=3)


Decision = Annotated[
    Act | Ask | Answer | Stop | InspectUI | OpenApplication | Steps, Field(discriminator="kind")
]
DECISION_ADAPTER = TypeAdapter(Decision)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Doppelte JSON-Schlüssel sind nicht erlaubt")
        result[key] = value
    return result


def parse_json(content: str):
    if len(content) > 16384:
        raise ValueError("Modellantwort ist zu groß")
    return json.loads(content, object_pairs_hook=_unique_object)


def parse_decision(content: str) -> Decision:
    return DECISION_ADAPTER.validate_python(parse_json(content))
