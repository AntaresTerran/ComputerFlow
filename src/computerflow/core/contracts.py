"""The complete 0.0.1 allowlist. No arbitrary input, apps, URLs or shell actions."""

import json
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from computerflow.core.config import StrictModel

Reference = Annotated[str, Field(min_length=1, max_length=256)]


class FocusWindow(StrictModel):
    type: Literal["focus_window"]
    context_id: Reference
    window_id: Reference


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


Action = Annotated[FocusWindow | SetVolume | MediaControl, Field(discriminator="type")]
ACTION_ADAPTER = TypeAdapter(Action)


class Act(StrictModel):
    kind: Literal["act"]
    action: Action


class Ask(StrictModel):
    kind: Literal["ask"]
    question: str = Field(min_length=1, max_length=500)


class Answer(StrictModel):
    kind: Literal["answer"]
    message: str = Field(min_length=1, max_length=500)


class Stop(StrictModel):
    kind: Literal["stop"]


Decision = Annotated[Act | Ask | Answer | Stop, Field(discriminator="kind")]
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
