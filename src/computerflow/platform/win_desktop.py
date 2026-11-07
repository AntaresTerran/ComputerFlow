"""Windows UI actions composed from Accessibility, bounded input and screen capture."""

import asyncio
import io
import re
import time
from ctypes import wintypes

from computerflow.brain.desktop import is_browser, safe_text
from computerflow.core.contracts import BrowserKey, UIElementAction, VisualClick, WriteText
from computerflow.core.errors import ComputerFlowError, PlatformError
from computerflow.core.jobs import State
from computerflow.platform.contracts import ActionResult, UIContext
from computerflow.platform.geometry import Rect
from computerflow.platform.win_input import WindowsInput
from computerflow.platform.win_screen import WindowsScreen
from computerflow.platform.win_uia import WindowsUIA

SHELL_PROCESSES = {
    "cmd",
    "powershell",
    "pwsh",
    "powershell_ise",
    "windowsterminal",
    "openconsole",
    "conhost",
    "wsl",
    "bash",
    "mintty",
    "wt",
    "regedit",
    "taskmgr",
    "mmc",
    "python",
    "pythonw",
}
BLOCKED_UI = re.compile(
    r"\b(?:powershell|terminal|eingabeaufforderung|command prompt|developer tools|"
    r"entwicklertools|devtools|ausführen|run new task|console|konsole)\b",
    re.I,
)
CHORDS = {
    "address": (0x11, 0x4C),
    "next_tab": (0x11, 9),
    "previous_tab": (0x11, 0x10, 9),
    "back": (0x12, 0x25),
    "forward": (0x12, 0x27),
    "reload": (0x11, 0x52),
}


def hwnd_for(window_id):
    return int(window_id.split(":", 1)[0], 16)


class WindowsDesktopUI:
    def __init__(self, platform, config):
        self.platform = platform
        self.config = config
        self.screen = WindowsScreen(platform.user32)
        self.input = WindowsInput(platform.user32)
        self._uia = None

    @property
    def uia(self):
        if self._uia is None:
            self._uia = WindowsUIA()
        return self._uia

    def excluded(self, window):
        names = (window.process_name, window.application, *window.app_aliases)
        return any(
            part.casefold() in name.casefold()
            for part in self.config.excluded_apps
            for name in names
        ) or any(part.casefold() in window.title.casefold() for part in self.config.excluded_titles)

    def target(self, window_id, *, require_foreground=True):
        if window_id is None or (require_foreground and self.platform.foreground_id() != window_id):
            raise PlatformError("Zielfenster muss im Vordergrund sein")
        hwnd = hwnd_for(window_id)
        window = self.platform._window(hwnd)
        if not window or window.id != window_id or not window.process_name:
            raise PlatformError("Windows-Fensteridentität konnte nicht geprüft werden")
        if self.excluded(window):
            raise PlatformError("Fenster ist durch einen Aufnahme- und UI-Ausschluss geschützt")
        if window.process_name.casefold().removesuffix(
            ".exe"
        ) in SHELL_PROCESSES or BLOCKED_UI.search(window.title):
            raise PlatformError("Dieses Fenster ist für automatisierte Eingabe gesperrt")
        return hwnd, window, self.screen.rect(hwnd)

    async def inspect(self, window_id, job):
        hwnd, window, rect = self.target(window_id)
        try:
            context = self.uia.inspect(hwnd, window, rect, job)
        except ComputerFlowError:
            raise
        except Exception:
            # A visual fallback may still be available for this allowed window.
            from uuid import uuid4

            return UIContext(uuid4().hex, window.id, time.monotonic())
        self.target(window.id)
        return context

    async def inspect_tabs(self, window_id, job):
        hwnd, window, rect = self.target(window_id, require_foreground=False)
        try:
            return self.uia.inspect_tabs(hwnd, window, rect, job)
        except ComputerFlowError:
            raise
        except Exception as exc:
            raise PlatformError(
                "Windows stellt die Registerkarten dieses Fensters nicht bereit"
            ) from exc

    def _check_capture(self, crop):
        platform = self.platform
        blocked = False

        @platform._enum_proc
        def visit(hwnd, _):
            nonlocal blocked
            if platform.user32.IsWindowVisible(hwnd) and not platform.user32.IsIconic(hwnd):
                window = platform._window(hwnd)
                if window and self.excluded(window):
                    try:
                        blocked = self.screen.rect(hwnd).intersect(crop) is not None
                    except PlatformError:
                        blocked = True
            return not blocked

        platform.user32.EnumWindows(visit, 0)
        if blocked:
            raise PlatformError(
                "Bildausschnitt überschneidet sich mit einem ausgeschlossenen Fenster"
            )

    def capture(self, window_id, *, at_cursor=False, ui=None):
        if not self.config.enabled:
            raise PlatformError("Bildschirmaufnahme ist deaktiviert")
        hwnd, window, _ = self.target(window_id)
        rect = self.screen.client_rect(hwnd)
        monitors = self.screen.monitors()
        cursor = self.screen.cursor()
        if self.config.monitor:
            monitors = monitors[self.config.monitor - 1 : self.config.monitor]
        candidates = [
            (key, bounds, crop) for key, bounds in monitors if (crop := bounds.intersect(rect))
        ]
        if at_cursor:
            if self.screen.at(cursor) != hwnd:
                raise PlatformError("Der Mauszeiger liegt nicht im aktiven Zielfenster")
            candidates = [item for item in candidates if item[2].contains(*cursor)]
        if len(candidates) > 1:
            candidates = [item for item in candidates if item[2].contains(*cursor)]
        if len(candidates) != 1:
            raise PlatformError("Welchen Monitor meinst du? Zeige auf den Fensterausschnitt.")
        key, bounds, crop = candidates[0]
        self._check_capture(crop)
        self.target(window_id)
        return self.screen.snapshot(window.id, key, bounds, crop, cursor, ui.elements if ui else ())

    def manual_capture(self):
        return self.capture(self.platform.foreground_id())

    async def preview_action(self, action, context, job):
        snapshot = context.screen
        hwnd, _, _ = self.target(action.window_id)
        point = snapshot.cursor if action.at_cursor else snapshot.crop.point(action.x, action.y)
        if self.screen.at(point) != hwnd:
            raise PlatformError("Vorgeschlagenes Klickziel liegt nicht im sichtbaren Zielfenster")
        marks = (
            [(n, e.rect.left, e.rect.top) for n, e in snapshot.marks[:12]]
            if self.config.show_marks
            else ()
        )
        await self.screen.preview(point, self.config.preview_ms, job, marks)

    def _check_element(self, action, context, job):
        hwnd, window, rect = self.target(action.window_id)
        element = next(e for e in context.ui.elements if e.id == action.element_id)
        if (
            isinstance(action, WriteText)
            and action.in_chat
            and not any(w.id == window.id and w.title == window.title for w in context.windows)
        ):
            raise PlatformError("Das Chatfenster hat sich geändert")
        if BLOCKED_UI.search(element.label) or element.label.casefold() in {"run", "execute"}:
            raise PlatformError("Dieses Element öffnet eine gesperrte Bedienoberfläche")
        item = self.uia.resolve(
            hwnd,
            window,
            rect,
            element,
            job,
            focused=isinstance(action, WriteText) and not action.focus_first,
        )
        self._check_surface(hwnd, item)
        focused = self.uia.focused(self.uia.client.ElementFromHandle(hwnd), window.pid)
        if (self.uia.runtime_id(focused) if focused else None) != context.ui.focus:
            raise PlatformError("Der Eingabefokus im Zielfenster hat sich geändert")
        return hwnd, window, rect, element, item

    def _check_surface(self, hwnd, item):
        root = self.uia.client.ElementFromHandle(hwnd)
        for _ in range(20):
            if not item or self.uia.client.CompareElements(root, item):
                return
            names = (item.CurrentName or "", item.CurrentAutomationId or "")
            if any(
                BLOCKED_UI.search(name) or name.casefold() in {"run", "execute"} for name in names
            ):
                raise PlatformError("Der Eingabebereich gehört zu einer gesperrten Oberfläche")
            item = self.uia.walker.GetParentElement(item)

    def _check_point_surface(self, hwnd, point):
        try:
            item = self.uia.client.ElementFromPoint(wintypes.POINT(*point))
        except (ImportError, OSError):
            return  # No semantic provider at this point; screen and user approval still apply.
        self._check_surface(hwnd, item)

    async def _verify(self, job, window_id, predicate):
        job.state = State.VERIFYING
        for _ in range(9):
            job.check()
            self.target(window_id)
            if predicate():
                return True
            await asyncio.sleep(0.06)
        return False

    async def execute(self, action, context, job):
        if isinstance(action, VisualClick):
            return await self._click(action, context, job)
        if isinstance(action, BrowserKey):
            return await self._browser(action, job)
        hwnd, window, rect, element, item = self._check_element(action, context, job)
        if isinstance(action, WriteText):
            return await self._write(action, hwnd, window, rect, item, element, job)
        if not isinstance(action, UIElementAction):
            raise PlatformError("Nicht unterstützte UI-Aktion")
        pattern = self.uia.pattern(item, element.operation)
        if not pattern:
            raise PlatformError("Accessibility-Aktion ist nicht mehr verfügbar")
        if element.operation == "toggle":
            previous = pattern.CurrentToggleState
            changed = lambda: pattern.CurrentToggleState != previous  # noqa: E731
            send = pattern.Toggle
        elif element.operation == "select":
            if pattern.CurrentIsSelected:
                return ActionResult(verified=True, message="Element ist bereits ausgewählt")
            changed = lambda: bool(pattern.CurrentIsSelected)  # noqa: E731
            send = pattern.Select
        else:

            def signature():
                state = self.uia.inspect(hwnd, window, rect, job)
                return (
                    self.platform._window(hwnd).title,
                    state.focus,
                    tuple((e.native_id, e.label, e.rect) for e in state.elements),
                )

            before = signature()
            changed = lambda: signature() != before  # noqa: E731
            send = pattern.Invoke
        job.check()
        self.target(action.window_id)
        job.executed.append(action.type)
        send()
        verified = await self._verify(job, action.window_id, changed)
        return ActionResult(
            verified=verified,
            message="Elementzustand geprüft"
            if verified
            else "Elementaktion gesendet. Windows meldet keine überprüfbare Zustandsänderung.",
        )

    async def _write(self, action, hwnd, window, rect, item, element, job):
        getter = self.uia.writable(item)
        if not getter or not safe_text(action.text):
            raise PlatformError("Textfeld ist nicht für die Eingabe freigegeben")
        root = self.uia.client.ElementFromHandle(hwnd)
        if action.focus_first:
            job.check()
            self.target(action.window_id)
            item.SetFocus()
            job.executed.append("focus_text_field")
            for _ in range(6):
                job.check()
                self.target(action.window_id)
                focused = self.uia.focused(root, window.pid)
                if focused and self.uia.runtime_id(focused) == element.native_id:
                    break
                await asyncio.sleep(0.04)
            else:
                raise PlatformError("Das eindeutige Textfeld konnte nicht fokussiert werden")
        before = getter()
        if not isinstance(before, str):
            raise PlatformError("Textfeldinhalt lässt sich nicht lokal prüfen")
        job.executed.append(action.type)
        for index, pair in enumerate(self.input.unicode(action.text)):
            job.check()
            self.target(action.window_id)
            focused = self.uia.focused(root, window.pid)
            if (
                not focused
                or self.uia.runtime_id(focused) != element.native_id
                or focused.CurrentIsPassword
            ):
                raise PlatformError("Eingabefokus hat sich geändert. Texteingabe unterbrochen.")
            self.input._check_modifiers()
            self.input.type_pair(pair)
            if index % 8 == 7:
                await asyncio.sleep(0)

        def received():
            actual = getter()
            return (
                isinstance(actual, str)
                and actual != before
                and actual.count(action.text) > before.count(action.text)
            )

        verified = await self._verify(job, action.window_id, received)
        return ActionResult(
            verified=verified,
            message="Text im geprüften Eingabefeld angekommen"
            if verified
            else "Texteingabe gesendet. Der vollständige Text konnte nicht bestätigt werden.",
        )

    async def _browser(self, action, job):
        hwnd, window, rect = self.target(action.window_id)
        if not is_browser(window):
            raise PlatformError(
                "Diese Tastenkombination ist nur in einem erkannten Browser erlaubt"
            )
        root = self.uia.client.ElementFromHandle(hwnd)

        def state():
            ui = self.uia.inspect(hwnd, window, rect, job)
            return (
                self.platform._window(hwnd).title,
                ui.focus,
                tuple((e.native_id, e.label) for e in ui.elements if e.operation != "write"),
            )

        before = state()
        self.target(window.id)
        job.check()
        job.executed.append(action.type)
        self.input.chord(CHORDS[action.key])

        def changed():
            if action.key == "address":
                focused = self.uia.focused(root, window.pid)
                if (
                    not focused
                    or focused.CurrentControlType != 50004
                    or not self.uia.writable(focused)
                ):
                    return False
                label = (focused.CurrentName or "").casefold()
                automation_id = (focused.CurrentAutomationId or "").casefold()
                return self.uia.runtime_id(focused) != before[1] or any(
                    term in label or term in automation_id
                    for term in ("adress", "address", "urlbar", "location")
                )
            return state() != before

        verified = await self._verify(job, window.id, changed)
        return ActionResult(
            verified=verified,
            message="Browserzustand geprüft"
            if verified
            else "Browserbefehl gesendet. Eine Zustandsänderung konnte nicht geprüft werden.",
        )

    async def _click(self, action, context, job):
        from PIL import Image

        snapshot = context.screen
        hwnd, _, _ = self.target(action.window_id)
        rect = self.screen.client_rect(hwnd)
        point = snapshot.cursor if action.at_cursor else snapshot.crop.point(action.x, action.y)
        if not snapshot.crop.contains(*point) or BLOCKED_UI.search(action.label):
            raise PlatformError("Visuelles Ziel liegt außerhalb des erlaubten Ausschnitts")
        initial_cursor = self.screen.cursor()
        x, y = point
        local = snapshot.crop.intersect(Rect(x - 24, y - 24, x + 25, y + 25))

        def check():
            job.check()
            current_hwnd, _, _ = self.target(action.window_id)
            current_rect = self.screen.client_rect(current_hwnd)
            if (
                current_rect != rect
                or current_rect.intersect(snapshot.monitor_bounds) != snapshot.crop
            ):
                raise PlatformError("Fenster oder Monitor hat sich seit der Aufnahme verschoben")
            if (snapshot.monitor_id, snapshot.monitor_bounds) not in self.screen.monitors():
                raise PlatformError("Der ursprüngliche Monitor ist nicht mehr verfügbar")
            if self.screen.at(point) != hwnd or self.screen.cursor() != initial_cursor:
                raise PlatformError("Das Klickziel ist verdeckt oder die Maus wurde übernommen")
            if initial_cursor != snapshot.cursor:
                raise PlatformError("Mausposition hat sich seit der Aufnahme geändert")
            self._check_capture(snapshot.crop)

        check()
        # Verify that the spot still looks like it did when the user approved it.
        original = Image.open(io.BytesIO(snapshot.png)).convert("RGB")
        scale_x = original.width / snapshot.crop.width
        scale_y = original.height / snapshot.crop.height
        image_bounds = (
            round((local.left - snapshot.crop.left) * scale_x),
            round((local.top - snapshot.crop.top) * scale_y),
            round((local.right - snapshot.crop.left) * scale_x),
            round((local.bottom - snapshot.crop.top) * scale_y),
        )
        old = original.crop(image_bounds)
        fresh = self.screen.grab(local)
        if _different(old, fresh, 0.20):
            raise PlatformError(
                "Bild am Klickziel hat sich geändert. Bitte nenne den Auftrag erneut."
            )
        if not self.input.user32.SetCursorPos(*point) or self.screen.at(point) != hwnd:
            raise PlatformError("Mauszeiger konnte nicht sicher auf das Ziel gesetzt werden")
        if initial_cursor != point:
            await job.guard(asyncio.sleep(0.075))
            self._check_capture(local)
            hovered = self.screen.grab(local)
            if _different(fresh, hovered, 0.30):
                raise PlatformError("Beim Zeigen hat sich das Klickziel deutlich geändert")
            fresh = hovered
        if self.screen.cursor() != point or self.screen.at(point) != hwnd:
            raise PlatformError("Maus oder Klickziel wurde vor der Ausführung übernommen")
        self._check_point_surface(hwnd, point)
        self.target(action.window_id)
        job.check()
        job.executed.append(action.type)
        self.input.click()
        verified = await self._verify(
            job,
            action.window_id,
            lambda: self._changed_at(local, fresh),
        )
        return ActionResult(
            verified=verified,
            message="Klick gesendet und sichtbare Änderung am Ziel geprüft"
            if verified
            else "Klick gesendet. Eine Änderung am Ziel konnte nicht geprüft werden.",
        )

    def _changed_at(self, crop, previous):
        self._check_capture(crop)
        return _different(previous, self.screen.grab(crop), 0.10)


def _different(before, after, ratio):
    from PIL import ImageChops

    difference = ImageChops.difference(before.resize((32, 32)), after.resize((32, 32)))
    changed = sum(1 for pixel in difference.getdata() if max(pixel) > 35)
    return changed > 32 * 32 * ratio
