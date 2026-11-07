"""Bounded UI Automation queries against the foreground window only."""

import re
import time
from uuid import uuid4

from computerflow.core.errors import PlatformError
from computerflow.platform.contracts import Element, UIContext
from computerflow.platform.geometry import Rect

# Control type / pattern IDs are stable UI Automation ABI constants.
ROLES = {
    50000: ("Schaltfläche", "invoke"),
    50002: ("Kontrollkästchen", "toggle"),
    50004: ("Textfeld", "write"),
    50005: ("Link", "invoke"),
    50007: ("Listeneintrag", "select"),
    50011: ("Menüpunkt", "invoke"),
    50013: ("Optionsfeld", "select"),
    50019: ("Registerkarte", "select"),
    50030: ("Dokument", "write"),
}
PATTERNS = {
    "invoke": (10000, "IUIAutomationInvokePattern"),
    "select": (10010, "IUIAutomationSelectionItemPattern"),
    "toggle": (10015, "IUIAutomationTogglePattern"),
    "value": (10002, "IUIAutomationValuePattern"),
    "text": (10014, "IUIAutomationTextPattern"),
}


class WindowsUIA:
    def __init__(self):
        from comtypes import COMError
        from comtypes.client import CreateObject, GetModule

        self._com_errors = (OSError, COMError)
        self.types = GetModule("UIAutomationCore.dll")
        self.client = CreateObject(
            "{E22AD333-B25F-460C-83D0-0581107395C9}",
            interface=self.types.IUIAutomation2,
        )
        self.client.ConnectionTimeout = 450
        self.client.TransactionTimeout = 450
        self.client.AutoSetFocus = False
        self.walker = self.client.ControlViewWalker

    def pattern(self, item, name):
        pattern, interface = PATTERNS[name]
        try:
            value = item.GetCurrentPattern(pattern)
            return value.QueryInterface(getattr(self.types, interface)) if value else None
        except self._com_errors:
            return None

    @staticmethod
    def runtime_id(item):
        return tuple(item.GetRuntimeId() or ())

    def focused(self, root, window_pid):
        item = self.client.GetFocusedElement()
        if not item or item.CurrentProcessId != window_pid:
            return None
        ancestor = item
        for _ in range(40):
            if self.client.CompareElements(ancestor, root):
                return item
            ancestor = self.walker.GetParentElement(ancestor)
            if not ancestor:
                break
        return None

    def element(self, item, window_rect, *, chat_root=None):
        role = ROLES.get(item.CurrentControlType)
        if (
            not role
            or not item.CurrentIsEnabled
            or item.CurrentIsOffscreen
            or item.CurrentIsPassword
        ):
            return None
        bounds = item.CurrentBoundingRectangle
        rect = Rect(bounds.left, bounds.top, bounds.right, bounds.bottom)
        if not window_rect.intersect(rect):
            return None
        name, operation = role
        label = (item.CurrentName or "").strip()[:150]
        if operation == "write":
            label = name  # The value of a text field is never its display label.
            if not item.CurrentIsKeyboardFocusable or self.writable(item) is None:
                return None
        elif not label or self.pattern(item, operation) is None:
            return None
        native_id = self.runtime_id(item)
        if not native_id:
            return None
        chat_input = (
            operation == "write" and chat_root is not None and self.is_chat(item, chat_root)
        )
        return Element(uuid4().hex, native_id, label, name, rect, operation, chat_input)

    def is_chat(self, item, root):
        try:
            for _ in range(12):
                if not item or self.client.CompareElements(item, root):
                    return False
                if re.search(r"\bchat\b", item.CurrentName or "", re.I):
                    return True
                item = self.walker.GetParentElement(item)
        except self._com_errors:
            return False
        return False

    def writable(self, item):
        if item.CurrentIsPassword:
            return None
        value = self.pattern(item, "value")
        if value and not value.CurrentIsReadOnly:
            return lambda: value.CurrentValue
        text = self.pattern(item, "text")
        readonly = text.DocumentRange.GetAttributeValue(40015) if text else None
        if type(readonly) in {bool, int} and readonly == 0:
            return lambda: text.DocumentRange.GetText(8192)
        return None

    def walk(self, root, deadline, check):
        item = self.walker.GetFirstChildElement(root)
        parents = []
        for _ in range(240):
            check()
            if not item or time.monotonic() > deadline:
                return
            yield item
            child = self.walker.GetFirstChildElement(item) if len(parents) < 18 else None
            if child:
                parents.append(item)
                item = child
                continue
            item = self.walker.GetNextSiblingElement(item)
            while not item and parents:
                item = self.walker.GetNextSiblingElement(parents.pop())

    def inspect(self, hwnd, window, rect, job):
        root = self.client.ElementFromHandle(hwnd)
        focused = self.focused(root, window.pid)
        focus = self.runtime_id(focused) if focused else None
        elements = {}
        complete = True
        count = 0
        deadline = time.monotonic() + 1.0
        candidates = self.walk(root, deadline, job.check)
        if focused:
            element = self.element(focused, rect, chat_root=root)
            if element:
                elements[element.native_id] = element
        for item in candidates:
            count += 1
            if item.CurrentProcessId != window.pid:
                continue
            try:
                element = self.element(item, rect)
            except self._com_errors:
                complete = False
                continue
            if element:
                elements.setdefault(element.native_id, element)
        return UIContext(
            uuid4().hex,
            window.id,
            time.monotonic(),
            tuple(elements.values()),
            focus,
            bool(focused and focused.CurrentIsPassword),
            complete and count < 240 and time.monotonic() < deadline,
        )

    def inspect_tabs(self, hwnd, window, rect, job):
        root = self.client.ElementFromHandle(hwnd)
        focused = self.focused(root, window.pid)
        focus = self.runtime_id(focused) if focused else None
        elements = []
        for item in self.walk(root, time.monotonic() + 0.7, job.check):
            if item.CurrentProcessId != window.pid or item.CurrentControlType != 50019:
                continue
            try:
                element = self.element(item, rect)
            except self._com_errors:
                continue
            if element:
                elements.append(element)
        return UIContext(uuid4().hex, window.id, time.monotonic(), tuple(elements), focus)

    def resolve(self, hwnd, window, rect, expected, job, *, focused=False):
        root = self.client.ElementFromHandle(hwnd)
        item = self.focused(root, window.pid)
        candidates = (item,) if focused else self.walk(root, time.monotonic() + 1, job.check)
        for candidate in candidates:
            if not candidate or candidate.CurrentProcessId != window.pid:
                continue
            if self.runtime_id(candidate) == expected.native_id:
                actual = self.element(
                    candidate, rect, chat_root=root if expected.chat_input else None
                )
                if (
                    actual
                    and (actual.label, actual.role, actual.rect, actual.operation)
                    == (
                        expected.label,
                        expected.role,
                        expected.rect,
                        expected.operation,
                    )
                    and actual.chat_input == expected.chat_input
                ):
                    return candidate
        raise PlatformError("UI-Element oder Eingabefokus hat sich geändert")
