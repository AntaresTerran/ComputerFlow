"""Application identity is independent of a document/folder window title."""

import ctypes
import re
from ctypes import wintypes
from dataclasses import dataclass
from functools import lru_cache
from pathlib import PureWindowsPath

TRANSLATIONS = {
    "notepad.exe": ("Editor", "Windows Editor", "Notepad"),
    "chatgpt.exe": ("ChatGPT", "Chat GPT", "Chat G P T"),
    "thunderbird.exe": ("Thunderbird",),
    "spotify.exe": ("Spotify",),
}
GENERIC_LABELS = {
    "electron",
    "chromium",
    "microsoft windows operating system",
    "windows",
    "betriebssystem microsoft windows",
}


@dataclass(frozen=True)
class ApplicationInfo:
    process_name: str
    name: str
    aliases: tuple[str, ...]


def application_info(process_name: str, labels: tuple[str, ...] = ()) -> ApplicationInfo:
    stem = PureWindowsPath(process_name).stem
    translated = TRANSLATIONS.get(process_name.casefold(), ())
    generic = {re.sub(r"\W", "", value.casefold()) for value in GENERIC_LABELS}
    names = tuple(
        dict.fromkeys(
            [
                *translated,
                *[
                    label
                    for label in labels
                    if not translated and re.sub(r"\W", "", label.casefold()) not in generic
                ],
                stem,
            ]
        )
    )
    return ApplicationInfo(process_name, names[0] if names else stem, names)


@lru_cache(maxsize=256)
def version_labels(executable: str) -> tuple[str, ...]:
    # Called only by the Windows adapter. No binary is loaded or executed.
    api = ctypes.WinDLL("version", use_last_error=True)
    api.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    api.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    api.GetFileVersionInfoW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    api.GetFileVersionInfoW.restype = wintypes.BOOL
    api.VerQueryValueW.argtypes = [
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.UINT),
    ]
    api.VerQueryValueW.restype = wintypes.BOOL
    unused = wintypes.DWORD()
    size = api.GetFileVersionInfoSizeW(executable, ctypes.byref(unused))
    if not 0 < size <= 4 * 1024**2:
        return ()
    buffer = ctypes.create_string_buffer(size)
    if not api.GetFileVersionInfoW(executable, 0, size, buffer):
        return ()
    pointer, length = ctypes.c_void_p(), wintypes.UINT()
    if not api.VerQueryValueW(
        buffer,
        r"\VarFileInfo\Translation",
        ctypes.byref(pointer),
        ctypes.byref(length),
    ):
        return ()
    translations = ctypes.cast(pointer, ctypes.POINTER(wintypes.WORD))
    codes = [
        (translations[2 * i], translations[2 * i + 1]) for i in range(min(length.value // 4, 8))
    ]
    result = []
    for language, codepage in codes:
        for field in ("ProductName", "FileDescription"):
            key = f"\\StringFileInfo\\{language:04x}{codepage:04x}\\{field}"
            if api.VerQueryValueW(buffer, key, ctypes.byref(pointer), ctypes.byref(length)):
                value = ctypes.wstring_at(pointer, min(max(0, length.value - 1), 128)).strip()
                if value and not re.search(r"[\x00-\x1f]", value):
                    result.append(value)
    return tuple(dict.fromkeys(result))
