"""Win32 input primitives with complete key pairs and explicit target checks at callers."""

import ctypes
from ctypes import wintypes as w

from computerflow.core.errors import PlatformError


class Keyboard(ctypes.Structure):
    _fields_ = [
        ("vk", w.WORD),
        ("scan", w.WORD),
        ("flags", w.DWORD),
        ("time", w.DWORD),
        ("extra", ctypes.c_size_t),
    ]


class Mouse(ctypes.Structure):
    _fields_ = [
        ("x", w.LONG),
        ("y", w.LONG),
        ("data", w.DWORD),
        ("flags", w.DWORD),
        ("time", w.DWORD),
        ("extra", ctypes.c_size_t),
    ]


class Payload(ctypes.Union):
    _fields_ = [("keyboard", Keyboard), ("mouse", Mouse)]


class Input(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("data", Payload)]


class WindowsInput:
    def __init__(self, user32):
        self.user32 = user32
        user32.SendInput.argtypes = [w.UINT, ctypes.POINTER(Input), ctypes.c_int]
        user32.SendInput.restype = w.UINT
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        user32.SetCursorPos.restype = w.BOOL

    def _send(self, inputs):
        buffer = (Input * len(inputs))(*inputs)
        return self.user32.SendInput(len(buffer), buffer, ctypes.sizeof(Input))

    def _check_modifiers(self):
        if any(
            self.user32.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x5B, 0x5C)
        ):
            raise PlatformError("Halte keine Umschalt-, Strg-, Alt- oder Windows-Taste gedrückt")

    @staticmethod
    def _keyboard(vk=0, scan=0, flags=0):
        return Input(1, Payload(keyboard=Keyboard(vk, scan, flags)))

    def unicode(self, text):
        self._check_modifiers()
        raw = text.encode("utf-16-le")
        for index in range(0, len(raw), 2):
            code = int.from_bytes(raw[index : index + 2], "little")
            yield (self._keyboard(scan=code, flags=4), self._keyboard(scan=code, flags=6))

    def chord(self, keys):
        self._check_modifiers()
        extended = {0x25, 0x27}
        downs = [self._keyboard(vk=key, flags=int(key in extended)) for key in keys]
        ups = [self._keyboard(vk=key, flags=2 | int(key in extended)) for key in reversed(keys)]
        sent = self._send(downs + ups)
        if sent != len(downs) + len(ups):
            if sent:
                held = min(sent, len(keys)) - max(0, sent - len(keys))
                if held:
                    self._send(ups[-held:])
            raise PlatformError("Windows hat die Tastenkombination abgewiesen")

    def type_pair(self, pair):
        sent = self._send(pair)
        if sent == 1:
            self._send(pair[1:])
        if sent != 2:
            raise PlatformError("Windows hat die Texteingabe abgewiesen")

    def click(self):
        self._check_modifiers()
        down = Input(0, Payload(mouse=Mouse(flags=2)))
        up = Input(0, Payload(mouse=Mouse(flags=4)))
        sent = self._send((down, up))
        if sent == 1:
            self._send((up,))
        if sent != 2:
            raise PlatformError("Windows hat den Mausklick abgewiesen")
