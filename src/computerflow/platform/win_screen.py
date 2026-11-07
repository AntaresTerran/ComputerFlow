"""Capture physical screen rectangles without grabbing unrelated parts of the desktop."""

import asyncio
import ctypes
import io
import time
from ctypes import wintypes as w
from uuid import uuid4

from computerflow.core.errors import PlatformError
from computerflow.platform.contracts import ScreenSnapshot
from computerflow.platform.geometry import Rect


class BitmapHeader(ctypes.Structure):
    _fields_ = [
        ("size", w.DWORD),
        ("width", w.LONG),
        ("height", w.LONG),
        ("planes", w.WORD),
        ("bits", w.WORD),
        ("compression", w.DWORD),
        ("image", w.DWORD),
        ("xppm", w.LONG),
        ("yppm", w.LONG),
        ("used", w.DWORD),
        ("important", w.DWORD),
    ]


def _api(dll, name, args, result):
    function = getattr(dll, name)
    function.argtypes = args
    function.restype = result
    return function


class WindowsScreen:
    def __init__(self, user32):
        self.u = user32
        g = ctypes.WinDLL("gdi32", use_last_error=True)
        _api(user32, "GetWindowRect", [w.HWND, ctypes.POINTER(w.RECT)], w.BOOL)
        _api(user32, "GetClientRect", [w.HWND, ctypes.POINTER(w.RECT)], w.BOOL)
        _api(user32, "ClientToScreen", [w.HWND, ctypes.POINTER(w.POINT)], w.BOOL)
        _api(user32, "GetCursorPos", [ctypes.POINTER(w.POINT)], w.BOOL)
        _api(user32, "WindowFromPoint", [w.POINT], w.HWND)
        _api(user32, "GetAncestor", [w.HWND, w.UINT], w.HWND)
        _api(user32, "GetDC", [w.HWND], w.HDC)
        _api(user32, "ReleaseDC", [w.HWND, w.HDC], ctypes.c_int)
        self.monitor_callback = ctypes.WINFUNCTYPE(
            w.BOOL, w.HANDLE, w.HDC, ctypes.POINTER(w.RECT), w.LPARAM
        )
        _api(
            user32,
            "EnumDisplayMonitors",
            [w.HDC, ctypes.POINTER(w.RECT), self.monitor_callback, w.LPARAM],
            w.BOOL,
        )
        _api(user32, "SetThreadDpiAwarenessContext", [w.HANDLE], w.HANDLE)
        _api(user32, "SetProcessDpiAwarenessContext", [w.HANDLE], w.BOOL)
        _api(
            user32,
            "SetWindowPos",
            [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT],
            w.BOOL,
        )
        user32.SetProcessDpiAwarenessContext(-4)  # Per-Monitor v2, before windows are created.
        self.g = g
        _api(g, "CreateCompatibleDC", [w.HDC], w.HDC)
        _api(
            g,
            "CreateDIBSection",
            [
                w.HDC,
                ctypes.POINTER(BitmapHeader),
                w.UINT,
                ctypes.POINTER(ctypes.c_void_p),
                w.HANDLE,
                w.DWORD,
            ],
            w.HANDLE,
        )
        _api(g, "SelectObject", [w.HDC, w.HANDLE], w.HANDLE)
        _api(
            g,
            "BitBlt",
            [
                w.HDC,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                w.HDC,
                ctypes.c_int,
                ctypes.c_int,
                w.DWORD,
            ],
            w.BOOL,
        )
        _api(g, "DeleteObject", [w.HANDLE], w.BOOL)
        _api(g, "DeleteDC", [w.HDC], w.BOOL)

    def physical(self):
        if not self.u.SetThreadDpiAwarenessContext(-4):
            raise PlatformError("Physische Monitor-Koordinaten sind nicht verfügbar")

    def rect(self, hwnd):
        self.physical()
        bounds = w.RECT()
        if not self.u.GetWindowRect(hwnd, ctypes.byref(bounds)):
            raise PlatformError("Fenstergrenzen nicht verfügbar")
        return Rect(bounds.left, bounds.top, bounds.right, bounds.bottom)

    def client_rect(self, hwnd):
        self.physical()
        client = w.RECT()
        point = w.POINT()
        if not self.u.GetClientRect(hwnd, ctypes.byref(client)) or not self.u.ClientToScreen(
            hwnd, ctypes.byref(point)
        ):
            raise PlatformError("Sichtbarer Fensterinhalt nicht verfügbar")
        return Rect(point.x, point.y, point.x + client.right, point.y + client.bottom)

    def cursor(self):
        self.physical()
        point = w.POINT()
        if not self.u.GetCursorPos(ctypes.byref(point)):
            raise PlatformError("Mausposition nicht verfügbar")
        return point.x, point.y

    def at(self, point):
        hwnd = self.u.WindowFromPoint(w.POINT(*point))
        return self.u.GetAncestor(hwnd, 2) if hwnd else None

    def monitors(self):
        self.physical()
        result = []

        @self.monitor_callback
        def collect(handle, _, rectangle, _data):
            rect = rectangle.contents
            result.append((f"{handle:x}", Rect(rect.left, rect.top, rect.right, rect.bottom)))
            return True

        if not self.u.EnumDisplayMonitors(None, None, collect, 0):
            raise PlatformError("Monitorgrenzen nicht verfügbar")
        return tuple(sorted(result, key=lambda item: (item[1].left, item[1].top)))

    def grab(self, area):
        from PIL import Image

        width, height = area.width, area.height
        if width <= 0 or height <= 0 or width * height > 32_000_000:
            raise PlatformError("Ungültige Größe des Bildausschnitts")
        self.physical()
        source = self.u.GetDC(None)
        target = bitmap = previous = None
        try:
            if not source:
                raise PlatformError("Windows-Bildschirmzugriff fehlt")
            target = self.g.CreateCompatibleDC(source)
            bits = ctypes.c_void_p()
            header = BitmapHeader(ctypes.sizeof(BitmapHeader), width, -height, 1, 32)
            bitmap = self.g.CreateDIBSection(
                source, ctypes.byref(header), 0, ctypes.byref(bits), None, 0
            )
            if not target or not bitmap or not bits:
                raise PlatformError("Bildspeicher konnte nicht bereitgestellt werden")
            previous = self.g.SelectObject(target, bitmap)
            if not previous or not self.g.BitBlt(
                target, 0, 0, width, height, source, area.left, area.top, 0x00CC0020
            ):
                raise PlatformError("Bildschirmaufnahme fehlgeschlagen")
            return Image.frombytes(
                "RGB", (width, height), ctypes.string_at(bits, width * height * 4), "raw", "BGRX"
            )
        finally:
            if previous:
                self.g.SelectObject(target, previous)
            if bitmap:
                self.g.DeleteObject(bitmap)
            if target:
                self.g.DeleteDC(target)
            if source:
                self.u.ReleaseDC(None, source)

    def snapshot(self, window_id, monitor_id, monitor, crop, cursor, elements):
        image = self.grab(crop)
        image.thumbnail((1280, 960))
        marks = tuple(
            enumerate((e for e in elements if crop.intersect(e.rect) and e.operation != "write"), 1)
        )[:35]
        output = io.BytesIO()
        image.save(output, format="PNG")
        return ScreenSnapshot(
            window_id=window_id,
            id=uuid4().hex,
            monitor_id=monitor_id,
            monitor_bounds=monitor,
            crop=crop,
            image_size=image.size,
            cursor=cursor,
            captured_at=time.monotonic(),
            png=output.getvalue(),
            marks=marks,
        )

    async def preview(self, point, duration, job, marks=()):
        if not duration:
            return
        u = self.u
        _api(
            u,
            "CreateWindowExW",
            [
                w.DWORD,
                w.LPCWSTR,
                w.LPCWSTR,
                w.DWORD,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                w.HWND,
                w.HMENU,
                w.HINSTANCE,
                w.LPVOID,
            ],
            w.HWND,
        )
        _api(u, "SetWindowDisplayAffinity", [w.HWND, w.DWORD], w.BOOL)
        _api(u, "DestroyWindow", [w.HWND], w.BOOL)
        _api(u, "UpdateWindow", [w.HWND], w.BOOL)
        x, y = point
        specs = [
            (x - 10, y - 10, 20, 3, ""),
            (x - 10, y + 7, 20, 3, ""),
            (x - 10, y - 7, 3, 14, ""),
            (x + 7, y - 7, 3, 14, ""),
        ]
        specs.extend((left, top, 24, 18, str(n)) for n, left, top in marks)
        overlays = []
        try:
            for left, top, width, height, text in specs:
                hwnd = u.CreateWindowExW(
                    0x080000A8,
                    "STATIC",
                    text,
                    0x80000000 | (1 if text else 6),
                    left,
                    top,
                    width,
                    height,
                    None,
                    None,
                    None,
                    None,
                )
                if not hwnd:
                    raise PlatformError("Klickvorschau konnte nicht angezeigt werden")
                overlays.append(hwnd)
                u.SetWindowDisplayAffinity(hwnd, 0x11)
                if not u.SetWindowPos(hwnd, -1, left, top, width, height, 0x50):
                    raise PlatformError("Klickvorschau konnte nicht positioniert werden")
                u.UpdateWindow(hwnd)
            await job.guard(asyncio.sleep(duration / 1000))
        finally:
            for hwnd in overlays:
                u.DestroyWindow(hwnd)
