"""Recognize explicit desktop commands before sharing any UI data with a model."""

import re
import unicodedata

from computerflow.brain.commands import SWITCH_VERB, command_body
from computerflow.brain.grounding import app_name_prefix, name_words, normalized_name
from computerflow.core.contracts import (
    Act,
    Ask,
    BrowserKey,
    InspectUI,
    OpenApplication,
    SetAppVolume,
    SetVolume,
    Steps,
    UIElementAction,
    WriteText,
)

_ONES = "null ein zwei drei vier fünf sechs sieben acht neun".split()
_TEENS = "zehn elf zwölf dreizehn vierzehn fünfzehn sechzehn siebzehn achtzehn neunzehn".split()
_TENS = "zwanzig dreißig vierzig fünfzig sechzig siebzig achtzig neunzig".split()
NUMBERS = {word: value for value, word in enumerate(_ONES + _TEENS)}
NUMBERS.update({word: value * 10 for value, word in enumerate(_TENS, 2)})
NUMBERS.update(
    {one + "und" + ten: NUMBERS[one] + NUMBERS[ten] for one in _ONES[1:] for ten in _TENS}
)
NUMBERS.update({"eins": 1, "hundert": 100, "einhundert": 100})
NUMBERS = {word.casefold(): value for word, value in NUMBERS.items()}
NUMBER = r"(?:\d{1,3}|[a-zäöüß]+(?:\s+und\s+[a-zäöüß]+)?)"
BROWSERS = {"firefox", "chrome", "msedge", "brave", "vivaldi", "opera", "chromium"}
STEP_BOUNDARY = re.compile(
    r"\s*(?:,\s*dann\s+|\s+und\s+dann\s+|\s+und\s+)"
    r"(?=(?:schreibe|tippe|klicke|klick|wechsel[et]?|wechsle|öffne|pausiere|setze|erhöhe|senke)\b)",
    re.I,
)
CURRENT_TEXT_SCOPE = (
    r"(?:(?:im|ins|in das)\s+(?:aktuelle[nms]?|aktive[nms]?|aktivierte[nms]?|"
    r"fokussierte[nms]?)\s+(?:textfeld|eingabefeld|fenster)\s+)"
)
TAB_VERB = rf"(?:{SWITCH_VERB}|gehe|springe|öffne|aktiviere|wähle)"
TAB_NAME = r"(?:tab|registerkarte)"
TAB_FORMS = (
    rf"(?:in\s+(?P<window>.{{1,120}}?)\s+)?(?:auf\s+(?:den|die)|in\s+(?:den|die)|"
    rf"zum|zur|zu\s+(?:dem|der)|den|die)\s+{TAB_NAME}\s+(?P<title>.{{1,150}})",
    rf"(?:(?:auf|in)\s+)?(?:den|die)\s+(?P<title>.{{1,150}}?)[- ]{TAB_NAME}"
    r"(?:\s+(?:von|in|bei)\s+(?P<window>.{1,120}))?",
    rf"(?:den|die)\s+(?P<window>.{{1,120}}?)[- ]{TAB_NAME}\s+(?:auf|zu)\s+(?P<title>.{{1,150}})",
    rf"in\s+(?P<window>.{{1,120}}?)\s+{TAB_NAME}\s+(?:auf|of|zu)\s+(?P<title>.{{1,150}})",
)


def has_tab_request(command: str) -> bool:
    return bool(
        re.match(
            rf"{TAB_VERB}\s+(?:bitte\s+)?"
            rf"(?!(?:zum|zu dem|in das|auf das)\s+fenster\b).*\b{TAB_NAME}\b",
            command_body(command),
            re.I,
        )
    )


def _number(raw: str) -> int | None:
    value = "".join(raw.casefold().split())
    return int(value) if value.isdecimal() else NUMBERS.get(value)


def _volume(text, context):
    match = re.fullmatch(
        rf"(?P<verb>setze|stelle|ändere|erhöhe|senke|verringere)\s+(?:die\s+)?"
        rf"(?P<scope>systemlautstärke|lautstärke)"
        rf"(?:\s+(?:von|für|in|bei)\s+(?P<app>.+?))?\s+"
        rf"(?P<mode>auf|um)\s+(?P<level>{NUMBER})\s*(?:%|prozent(?:punkte)?)",
        text,
        re.I,
    )
    if not match:
        return None
    value = _number(match["level"])
    if value is None or not 0 <= value <= 100:
        return Ask(kind="ask", question="Welche Lautstärke zwischen 0 und 100 Prozent meinst du?")
    app = match["app"]
    if app and match["scope"].casefold() == "systemlautstärke":
        return Ask(kind="ask", question="Meinst du die Systemlautstärke oder die einzelne App?")
    if app:
        key = normalized_name(app)
        matches = [
            s
            for s in context.audio_sessions
            if key in {normalized_name(n) for n in (s.app, *s.aliases)}
        ]
        if not matches:
            matches = [
                s
                for s in context.audio_sessions
                if any(app_name_prefix(key, n) for n in (s.app, *s.aliases))
            ]
        if len(matches) != 1:
            return Ask(kind="ask", question=f"Welche aktive Wiedergabe von „{app}“ meinst du?")
        session = matches[0]
        current = session.level
    else:
        if context.volume is None or not context.volume_device_id:
            return Ask(kind="ask", question="Die Systemlautstärke ist momentan nicht verfügbar.")
        current = context.volume
    if match["mode"].casefold() == "um":
        verb = match["verb"].casefold()
        if verb not in {"erhöhe", "senke", "verringere"}:
            return Ask(kind="ask", question="Soll die Lautstärke steigen oder sinken?")
        value = max(0, min(100, current + (value if verb == "erhöhe" else -value)))
    if app:
        return Act(
            kind="act",
            action=SetAppVolume(
                type="set_app_volume",
                context_id=context.id,
                session_id=session.id,
                level=value,
            ),
        )
    return Act(
        kind="act",
        action=SetVolume(
            type="set_volume",
            context_id=context.id,
            device_id=context.volume_device_id,
            level=value,
        ),
    )


def parse_desktop(command, context):
    text = command_body(command)
    text = re.sub(
        r"^(?:verwende|benutze|nutze)\s+das\s+"
        r"(?:aktuelle|aktive|fokussierte)\s+(?:textfeld|eingabefeld)\s+und\s+"
        r"(?=(?:schreibe|tippe)\s)",
        "",
        text,
        flags=re.I,
    )
    # Once text entry starts, everything after its verb is content, including “und dann”.
    parts = []
    rest = text
    while len(parts) < 3 and not re.match(r"(?:schreibe|tippe)\s", rest, re.I):
        boundary = STEP_BOUNDARY.search(rest)
        if not boundary:
            break
        parts.append(rest[: boundary.start()])
        rest = rest[boundary.end() :]
    if len(parts) >= 3:
        return Ask(kind="ask", question="Bitte nenne höchstens drei Schritte pro Auftrag.")
    if parts:
        return Steps(kind="steps", commands=tuple((*parts, rest)))

    chat = re.fullmatch(
        r"(?:schreibe|tippe)\s+(?:in den|in dem|im)\s+(?:(?P<source>.{1,80}?)[- ])?"
        r"chat(?:\s*:\s*|\s+)(?P<value>.+)",
        text,
        re.I,
    ) or re.fullmatch(
        r"(?:schreibe|tippe)\s+(?P<value>.+?)\s+(?:in den|in dem|im)\s+"
        r"(?:(?P<source>.{1,80}?)[- ])?(?:chat|stream)[.!?]?",
        text,
        re.I,
    )
    writing = chat or re.fullmatch(
        rf"(?:schreibe|tippe)(?:\s+den text)?\s+{CURRENT_TEXT_SCOPE}?(?P<value>.+)",
        text,
        re.I,
    )
    if writing:
        value = writing["value"]
        if (
            value.startswith("„")
            and value.endswith("“")
            or value.startswith('"')
            and value.endswith('"')
        ):
            value = value[1:-1]
        if safe_text(value):
            return InspectUI(
                kind="inspect_ui",
                operation="chat" if chat else "write",
                value=value,
                source=chat["source"] if chat else None,
            )
        return Ask(kind="ask", question="Bitte nenne einen einzeiligen Text zum Einfügen.")

    text = text.rstrip(".!? ")
    for form in TAB_FORMS:
        tab = re.fullmatch(rf"(?:bitte\s+)?{TAB_VERB}\s+(?:bitte\s+)?{form}", text, re.I)
        if tab:
            return InspectUI(
                kind="inspect_ui",
                operation="tab",
                value=tab["title"].strip('"„“') or tab["title"],
                window=tab["window"],
            )
    stream = re.fullmatch(
        rf"{SWITCH_VERB}\s+(?:den\s+)?(.{{1,80}}?)[- ]stream\s+(?:auf|zu)\s+(.{{1,150}})",
        text,
        re.I,
    )
    if stream:
        return InspectUI(kind="inspect_ui", operation="stream", value=stream[2], source=stream[1])
    launch = re.fullmatch(r"(?:öffne|starte)\s+(?:(?:den|das|die)\s+)?(.{1,150})", text, re.I)
    if (
        launch
        and not has_tab_request(text)
        and not re.match(r"(?:wiedergabe|musik)\b", launch[1], re.I)
    ):
        name = launch[1].strip('"„“')
        if safe_text(name) and not re.search(r"\b(?:nicht|kein(?:e|en)?|niemals)\b", name, re.I):
            return OpenApplication(kind="open_application", name=name)
    volume = _volume(text, context)
    if volume is not None:
        return volume
    pointer = re.fullmatch(
        r"klick(?:e)?\s+(?:bitte\s+)?(?:hier|da|dort|an der maus|wohin ich zeige)", text, re.I
    )
    if pointer:
        return InspectUI(kind="inspect_ui", operation="cursor", value="Mauszeiger")
    click = re.fullmatch(
        r"klick(?:e)?\s+(?:in|bei)\s+(?P<window>.{1,120}?)\s+auf\s+(?P<label>.{1,150})",
        text,
        re.I,
    ) or re.fullmatch(
        r"(?:klick(?:e)?\s+auf|drücke|wähle)\s+(?P<label>.{1,150}?)(?:\s+im\s+fenster\s+"
        r"(?P<window>.{1,120}))?",
        text,
        re.I,
    )
    if click:
        label = re.sub(r"^(?:den|die|das)\s+", "", click["label"], flags=re.I)
        label = re.sub(
            r"^(?:schaltfläche|button|registerkarte|menüpunkt)\s+", "", label, flags=re.I
        )
        label = label.strip('"„“')
        if not safe_text(label):
            return Ask(kind="ask", question="Welches sichtbare Element meinst du?")
        return InspectUI(
            kind="inspect_ui", operation="activate", value=label, window=click["window"]
        )

    browser = re.fullmatch(
        r"(?:fokussiere (?:die )?adressleiste|(?:zum |wechsle zum )?nächsten tab|"
        r"(?:zum |wechsle zum )?vorherigen tab|(?:gehe )?(?:im browser )?(?:zurück|vorwärts)|"
        r"lade (?:die )?seite neu)",
        text,
        re.I,
    )
    if browser:
        window = next((w for w in context.windows if w.id == context.foreground_id), None)
        if not window or not is_browser(window):
            return Ask(kind="ask", question="Welcher Browser soll für diesen Schritt aktiv sein?")
        lower = text.casefold()
        key = next(
            key
            for word, key in (
                ("adressleiste", "address"),
                ("nächsten tab", "next_tab"),
                ("vorherigen tab", "previous_tab"),
                ("zurück", "back"),
                ("vorwärts", "forward"),
                ("neu", "reload"),
            )
            if word in lower
        )
        return Act(
            kind="act",
            action=BrowserKey(
                type="browser_key", context_id=context.id, window_id=window.id, key=key
            ),
        )
    return None


def is_browser(window) -> bool:
    return window.process_name.casefold().removesuffix(".exe") in BROWSERS


def matching_app_windows(windows, name):
    target = normalized_name(name)
    if not target:
        return []

    def labels(window):
        return (
            window.application,
            window.process_name.casefold().removesuffix(".exe"),
            *window.app_aliases,
        )

    exact = [window for window in windows if target in {normalized_name(n) for n in labels(window)}]
    return exact or [
        window for window in windows if any(app_name_prefix(target, n) for n in labels(window))
    ]


def named_tab_reply(text, context):
    words = text.split()
    apps = {
        normalized_name(name)
        for window in context.windows
        for name in (
            window.application,
            window.process_name.casefold().removesuffix(".exe"),
            *window.app_aliases,
        )
        if name
    }
    for index in range(len(words) - 1, 0, -1):
        window, title = " ".join(words[:index]), " ".join(words[index:])
        if len(window) <= 120 and len(title) <= 150 and normalized_name(window) in apps:
            return InspectUI(
                kind="inspect_ui", operation="tab", value=title, window=window, exact_tab=True
            )
    return None


def matching_surface_windows(windows, name):
    apps = matching_app_windows(windows, name)
    key = name_words(name)
    return [w for w in windows if w in apps or (key and f" {key} " in f" {name_words(w.title)} ")]


def matching_tabs(request: InspectUI, candidates):
    label = name_words(request.value)
    if not label:
        return []
    names = [
        (ui, element, name_words(element.label))
        for ui in candidates
        for element in ui.elements
        if element.role == "Registerkarte" and element.operation == "select"
    ]
    if request.operation == "stream":
        source = name_words(request.source or "")
        names = [
            (ui, element, name)
            for ui, element, name in names
            if source and f" {source} " in f" {name} "
        ]
    exact = [(ui, element) for ui, element, name in names if name == label]
    return exact or [(ui, element) for ui, element, name in names if f" {label} " in f" {name} "]


def safe_text(text: str) -> bool:
    return 1 <= len(text) <= 500 and all(
        char in {"\u200c", "\u200d"}
        or (unicodedata.category(char)[0] != "C" and char not in {"\u2028", "\u2029"})
        for char in text
    )


def bind_element(request: InspectUI, context):
    ui = context.ui
    if not ui:
        return None
    if request.operation in {"write", "chat"}:
        if ui.protected_focus:
            return Ask(
                kind="ask",
                question="Das fokussierte Feld ist geschützt. Wähle ein gewöhnliches Textfeld.",
            )
        writable = [element for element in ui.elements if element.operation == "write"]
        target = next((e for e in writable if e.native_id == ui.focus), None)
        in_chat = request.operation == "chat"
        if in_chat and (target is None or not target.chat_input):
            return Ask(kind="ask", question="Setze den Cursor ins Nachrichtenfeld des Chats.")
        focus_first = not in_chat and target is None and len(writable) == 1 and ui.complete
        if focus_first:
            target = writable[0]
        if target is None:
            return Ask(
                kind="ask",
                question="Welches Textfeld soll ich verwenden? Setze zuerst den Eingabefokus.",
            )
        return Act(
            kind="act",
            action=WriteText(
                type="write_text",
                context_id=context.id,
                window_id=ui.window_id,
                ui_id=ui.id,
                element_id=target.id,
                text=request.value,
                focus_first=focus_first,
                in_chat=in_chat,
            ),
        )
    if request.operation != "activate":
        return None
    label = name_words(request.value)
    options = [element for element in ui.elements if element.operation != "write"]
    matches = [element for element in options if name_words(element.label) == label]
    if not matches and label:
        matches = [e for e in options if f" {label} " in f" {name_words(e.label)} "]
    if len(matches) > 1:
        return Ask(
            kind="ask",
            question=f"Welches der {len(matches)} Elemente mit „{request.value}“ meinst du?",
        )
    if not matches:
        return None
    return Act(
        kind="act",
        action=UIElementAction(
            type="ui_element",
            context_id=context.id,
            window_id=ui.window_id,
            ui_id=ui.id,
            element_id=matches[0].id,
        ),
    )
