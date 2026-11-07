"""Model-native names become context-bound actions through deterministic grounding."""

import re
from difflib import SequenceMatcher
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from computerflow.core.config import StrictModel
from computerflow.core.contracts import (
    Act,
    Answer,
    Ask,
    FocusWindow,
    InspectUI,
    MediaControl,
    SetVolume,
    Stop,
)
from computerflow.platform.contracts import DesktopContext


class FocusIntent(StrictModel):
    type: Literal["focus_window"]
    target: str = Field(min_length=1, max_length=256)


class TabIntent(StrictModel):
    type: Literal["select_tab"]
    target: str = Field(min_length=1, max_length=150)
    window: str | None = Field(min_length=1, max_length=120)


class VolumeIntent(StrictModel):
    type: Literal["set_volume"]
    level: int = Field(ge=0, le=100)


class MediaIntent(StrictModel):
    type: Literal["media_control"]
    target: str | None = Field(default=None, min_length=1, max_length=256)
    operation: Literal["play", "pause"]


class IntentAct(StrictModel):
    kind: Literal["act"]
    action: Annotated[
        FocusIntent | TabIntent | VolumeIntent | MediaIntent, Field(discriminator="type")
    ]


class IntentAsk(StrictModel):
    kind: Literal["ask"]
    question: str = Field(min_length=1, max_length=500)


Intent = Annotated[IntentAct | IntentAsk | Answer | Stop, Field(discriminator="kind")]
INTENT_ADAPTER = TypeAdapter(Intent)


def normalized_name(value: str) -> str:
    # German ASR often splits compounds/app names: "Computer Flow Test Fenster".
    return re.sub(r"[\W_]", "", value.casefold())


def name_words(value: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", value.casefold()))


def app_name_prefix(target: str, label: str) -> bool:
    # Native metadata may expose a longer product name, e.g. a component name.
    # Match leading whole words only. Similar-sounding names still need a question.
    words = re.findall(r"[^\W_]+", label.casefold())
    return len(target) >= 3 and any(target == "".join(words[:i]) for i in range(1, len(words)))


def application_vocabulary(context: DesktopContext) -> tuple[str, ...]:
    result = {}
    names = [window.application for window in context.windows]
    names += [name for session in context.media_sessions for name in session.app_aliases]
    for name in names:
        if name and len(name) <= 64 and len(name.split()) <= 5:
            result.setdefault(normalized_name(name), name)
    return tuple(result.values())[:32]


def ground(intent: Intent, context: DesktopContext, command: str):
    if not isinstance(intent, IntentAct):
        return intent
    action = intent.action
    if isinstance(action, TabIntent):
        spoken = f" {name_words(command)} "
        names = [action.target, action.window] if action.window else [action.target]
        if any(not name_words(name) or f" {name_words(name)} " not in spoken for name in names):
            return Ask(
                kind="ask",
                question="Wie heißt die gewünschte Registerkarte im Fenster?",
                reply="tab",
            )
        return InspectUI(
            kind="inspect_ui", operation="tab", value=action.target, window=action.window
        )
    requested_target = getattr(action, "target", None)
    if requested_target and normalized_name(requested_target) not in normalized_name(command):
        return Ask(
            kind="ask", question="Bitte nenne den gewünschten Fenster- oder App-Namen eindeutig."
        )
    if isinstance(action, FocusIntent):
        target = normalized_name(action.target)
        matches = []
        if target:
            matches = [
                w
                for w in context.windows
                if target == normalized_name(w.title)
                or any(
                    target == normalized_name(name)
                    for name in (
                        w.application,
                        w.process_name.casefold().removesuffix(".exe"),
                        *w.app_aliases,
                    )
                )
            ]
            if not matches:
                matches = [
                    w
                    for w in context.windows
                    if any(
                        app_name_prefix(target, label) for label in (w.application, *w.app_aliases)
                    )
                    or target in normalized_name(w.title)
                ]
        if len(matches) != 1:
            if not matches:
                names = application_vocabulary(context)
                suggestions = [
                    name
                    for name in names
                    if len(target) >= 4
                    and (
                        SequenceMatcher(None, target, normalized_name(name)).ratio() >= 0.75
                        or SequenceMatcher(
                            None, target, normalized_name(name)[: len(target)]
                        ).ratio()
                        >= 0.75
                    )
                ]
                if suggestions:
                    return Ask(
                        kind="ask",
                        reply="window",
                        question="Meinst du "
                        + ", ".join(f"„{name}“" for name in suggestions[:3])
                        + "? Sag bitte, welches Fenster oder welche Anwendung du meinst.",
                    )
            return Ask(
                kind="ask",
                reply="window",
                question=(
                    f"Welches Fenster meinst du mit „{action.target}“? "
                    + (
                        "Mehrere Fenstertitel passen."
                        if matches
                        else "Kein Programmname oder Fenstertitel passt eindeutig."
                    )
                ),
            )
        return Act(
            kind="act",
            action=FocusWindow(
                type="focus_window",
                context_id=context.id,
                window_id=matches[0].id,
            ),
        )
    if isinstance(action, VolumeIntent):
        if not context.volume_device_id:
            return Answer(kind="answer", message="Systemlautstärke ist nicht verfügbar.")
        return Act(
            kind="act",
            action=SetVolume(
                type="set_volume",
                context_id=context.id,
                device_id=context.volume_device_id,
                level=action.level,
            ),
        )
    matches = [
        s
        for s in context.media_sessions
        if (
            not action.target
            or any(
                normalized_name(action.target) in normalized_name(alias)
                for alias in (s.app, *s.app_aliases)
            )
        )
        and (
            getattr(s, f"can_{action.operation}")
            or s.status == ("playing" if action.operation == "play" else "paused")
        )
    ]
    if len(matches) != 1:
        return Ask(
            kind="ask",
            reply=action.operation,
            question="Welche Anwendung soll ich abspielen oder pausieren? "
            "Das Wiedergabeziel ist nicht eindeutig verfügbar.",
        )
    return Act(
        kind="act",
        action=MediaControl(
            type="media_control",
            context_id=context.id,
            session_id=matches[0].id,
            operation=action.operation,
        ),
    )
