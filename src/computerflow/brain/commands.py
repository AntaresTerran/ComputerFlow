"""Small, anchored command forms keep clear media requests in the correct action family."""

import re

from computerflow.brain.grounding import FocusIntent, IntentAct, MediaIntent

SWITCH_VERB = r"(?:wechsel[ent]?|wechsele|wechsle)"


def command_body(command: str) -> str:
    text = re.sub(r"^computer\s*[,!:]?\s+", "", command.strip(), flags=re.I)
    return re.sub(r"^(?:(?:dann|bitte|ich)\s+)+", "", text, flags=re.I)


def is_stop_request(command: str) -> bool:
    return bool(
        re.match(r"^(?:stopp?|abbrechen|abrechen)(?:\s*[.!?;,:]|\s*$)", command_body(command), re.I)
    )


def parse_explicit_command(command: str):
    text = re.sub(r"\s+bitte$", "", command_body(command).rstrip(".!? "), flags=re.I)
    if re.search(r"\b(?:nicht|kein|keine|keinen|never|don't)\b", text, re.I):
        return None
    media_patterns = (
        (r"(?P<target>.+?)\s*[,;:]?\s+(?:pause|pausieren)", "pause"),
        (r"(?P<target>.+?)\s*[,;:]?\s+(?:play|abspielen|fortsetzen)", "play"),
        (
            r"(?:pausiere|pausieres|pausier|pausieren|pause)(?:\s+(?:die\s+)?(?:wiedergabe|musik))?"
            r"(?:\s+(?:(?:in|im|bei|von|auf)\s+)?(?P<target>.+))?",
            "pause",
        ),
        (
            r"(?:starte|beginne)\s+(?:die\s+)?wiedergabe"
            r"(?:\s+(?:(?:in|im|bei|von|auf)\s+)?(?P<target>.+))?",
            "play",
        ),
        (r"(?:spiele|spiel)\s+(?P<target>.+?)\s+ab", "play"),
        (r"(?:play|abspielen|fortsetzen)(?:\s+(?P<target>.+))?", "play"),
    )
    for pattern, operation in media_patterns:
        match = re.fullmatch(pattern, text, re.I)
        if match:
            target = match.groupdict().get("target")
            if target and len(target) > 256:
                return None
            return IntentAct(
                kind="act",
                action=MediaIntent(
                    type="media_control",
                    operation=operation,
                    target=target.strip(" ,;:") if target else None,
                ),
            )
    focus = re.fullmatch(
        rf"(?:{SWITCH_VERB}|fokussiere|aktiviere|zeige)\s+(?:bitte\s+)?"
        r"(?:(?:zu|zum|zur|auf|in)\s+)?(?:(?:das|die|den|der|dem)\s+)?"
        r"(?:(?:fenster|app|anwendung|programm)\s+(?:von\s+)?)?(?P<target>.+)",
        text,
        re.I,
    )
    if focus:
        if len(focus["target"]) > 256:
            return None
        return IntentAct(
            kind="act",
            action=FocusIntent(
                type="focus_window",
                target=focus["target"].strip(),
            ),
        )
    return None


def has_focus_request(command: str) -> bool:
    return bool(
        re.search(r"\b(?:wechsel\w*|wechsle|fokussier\w*|aktivier\w*|zeige|öffne)\b", command, re.I)
    )


def has_media_request(command: str, operation: str) -> bool:
    if re.search(r"\b(?:nicht|kein|keine|keinen|never|don't)\b", command, re.I):
        return False
    words = (
        r"paus\w*|anhalten|stoppe|stoppen|unterbrich"
        if operation == "pause"
        else r"play|abspiel\w*|spiel\w*|fortsetz\w*|weiter|wiedergabe|resume"
    )
    return bool(re.search(r"\b(?:" + words + r")\b", command, re.I))


def has_volume_request(command: str) -> bool:
    return bool(re.search(r"\b(?:\w*lautstärk\w*|lauter|leiser|volume|stumm)\b", command, re.I))
