"""Discover and invoke registered Windows applications without a command line."""

import ctypes
import re
from ctypes import wintypes

from computerflow.core.errors import PlatformError
from computerflow.platform.contracts import RegisteredApplication

BLOCKED = re.compile(
    r"powershell|terminal|commandprompt|eingabeaufforderung|regedit|registrierungseditor|"
    r"cmd\.exe|taskmgr|taskmanager|wsl\.exe|bash\.exe|systemsettings|windowssettings|"
    r"systemsteuerung|devtools|entwicklertools|windowsmanagement",
    re.I,
)


class WindowsApps:
    def __init__(self):
        from comtypes.client import CreateObject

        self.shell = CreateObject("Shell.Application", dynamic=True)

    def entries(self, job):
        folder = self.shell.NameSpace("shell:AppsFolder")
        if not folder:
            raise PlatformError("Windows-Anwendungskatalog nicht verfügbar")
        items = folder.Items()
        if items.Count > 1024:
            raise PlatformError("Windows-Anwendungskatalog überschreitet die Suchgrenze")
        for index in range(items.Count):
            job.check()
            item = items.Item(index)
            name = (item.Name or "").strip()
            registration = (item.Path or "").strip()
            if not 0 < len(name) <= 150 or not 0 < len(registration) <= 256:
                continue
            if BLOCKED.search(registration) or BLOCKED.search(re.sub(r"[\W_]", "", name)):
                continue
            yield RegisteredApplication(id=registration, name=name), item

    def launch(self, registration, job, check_foreground):
        matches = [item for app, item in self.entries(job) if app == registration]
        if len(matches) != 1:
            raise PlatformError("Die registrierte Anwendung ist nicht mehr eindeutig verfügbar")
        check_foreground()
        matches[0].InvokeVerb("open")


def package_app_id(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    query = kernel.GetApplicationUserModelId
    query.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.UINT), wintypes.LPWSTR]
    query.restype = wintypes.LONG
    process = kernel.OpenProcess(0x1000, False, pid)
    if not process:
        return ""
    try:
        value = ctypes.create_unicode_buffer(256)
        size = wintypes.UINT(len(value))
        return value.value if query(process, ctypes.byref(size), value) == 0 else ""
    finally:
        kernel.CloseHandle(process)
