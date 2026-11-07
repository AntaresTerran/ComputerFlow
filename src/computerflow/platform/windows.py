"""Native Windows focus, Core Audio volume and targeted SMTC playback.

No generic keyboard, mouse, shell or application-launch primitive is exposed.
"""

import asyncio
import ctypes
import sys
import time
from ctypes import wintypes
from importlib import import_module
from uuid import uuid4

import psutil

from computerflow.brain.desktop import matching_app_windows
from computerflow.core.config import VisionConfig
from computerflow.core.contracts import (
    Action,
    BrowserKey,
    FocusWindow,
    LaunchApplication,
    MediaControl,
    SetAppVolume,
    SetVolume,
    UIElementAction,
    VisualClick,
    WriteText,
)
from computerflow.core.errors import ComputerFlowError, PlatformError
from computerflow.core.jobs import Job, State
from computerflow.platform.applications import ApplicationInfo, application_info, version_labels
from computerflow.platform.contracts import (
    ActionResult,
    AudioSession,
    DesktopContext,
    MediaSession,
    Window,
)
from computerflow.platform.win_apps import WindowsApps, package_app_id
from computerflow.platform.win_desktop import WindowsDesktopUI


class WindowsPlatform:
    def __init__(self, vision: VisionConfig | None = None):
        if sys.platform != "win32":
            raise PlatformError("Reale Desktopaktionen sind nur auf Windows verfügbar")
        # WinRT callbacks need MTA when the CLI does not run an STA message pump.
        if "comtypes" not in sys.modules:
            sys.coinit_flags = 0
            # PortAudio can initialize STA while opening the microphone. Establish
            # MTA now, before Recorder.open(), rather than at the first snapshot.
            try:
                import_module("comtypes")
            except ImportError:
                pass  # Window-only callers may omit the optional desktop extra.
            except OSError as exc:
                raise PlatformError(
                    "Windows-Audio wurde im falschen Threadmodus initialisiert; "
                    "ComputerFlow in einem frischen Prozess starten"
                ) from exc
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        u = self.user32
        self._enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        u.EnumWindows.argtypes = [self._enum_proc, wintypes.LPARAM]
        u.EnumWindows.restype = wintypes.BOOL
        u.IsWindowVisible.argtypes = [wintypes.HWND]
        u.IsWindowVisible.restype = wintypes.BOOL
        u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        u.GetWindowTextLengthW.restype = ctypes.c_int
        u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindowTextW.restype = ctypes.c_int
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD
        u.GetForegroundWindow.argtypes = []
        u.GetForegroundWindow.restype = wintypes.HWND
        u.SetForegroundWindow.argtypes = [wintypes.HWND]
        u.SetForegroundWindow.restype = wintypes.BOOL
        u.IsIconic.argtypes = [wintypes.HWND]
        u.IsIconic.restype = wintypes.BOOL
        u.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
        u.ShowWindowAsync.restype = wintypes.BOOL
        self._media_targets: dict[str, tuple[str, object]] = {}
        self._media_context_id: str | None = None
        self._applications: dict[int, ApplicationInfo] = {}
        self._audio_targets = {}
        self._audio_context_id = None
        self.ui = WindowsDesktopUI(self, vision or VisionConfig())
        self._apps = None

    async def inspect_ui(self, window_id, job):
        return await self.ui.inspect(window_id, job)

    async def inspect_tabs(self, window_id, job):
        return await self.ui.inspect_tabs(window_id, job)

    @property
    def apps(self):
        if self._apps is None:
            self._apps = WindowsApps()
        return self._apps

    async def registered_apps(self, job):
        return tuple(app for app, _ in self.apps.entries(job))

    def capture(self, window_id, *, at_cursor=False, ui=None):
        return self.ui.capture(window_id, at_cursor=at_cursor, ui=ui)

    def manual_capture(self):
        return self.ui.manual_capture()

    async def preview_action(self, action, context, job):
        await self.ui.preview_action(action, context, job)

    def _application(self, pid: int) -> ApplicationInfo:
        if pid not in self._applications:
            try:
                process = psutil.Process(pid)
                name = process.name()
                try:
                    labels = version_labels(process.exe())
                except (OSError, psutil.Error):
                    labels = ()
                self._applications[pid] = application_info(name, labels)
            except psutil.Error:
                self._applications[pid] = ApplicationInfo("", "", ())
        return self._applications[pid]

    def _window(self, hwnd: int) -> Window | None:
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        text = ctypes.create_unicode_buffer(513)
        self.user32.GetWindowTextW(hwnd, text, len(text))
        app = self._application(pid.value)
        return Window(
            id=f"{hwnd:x}:{pid.value}",
            title=text.value,
            pid=pid.value,
            application=app.name,
            process_name=app.process_name,
            app_aliases=app.aliases,
        )

    def foreground_id(self) -> str | None:
        window = self._window(self.user32.GetForegroundWindow())
        return window.id if window else None

    def context_is_current(self, context: DesktopContext) -> bool:
        return self.foreground_id() == context.foreground_id

    def windows(self) -> tuple[Window, ...]:
        result = []

        @self._enum_proc
        def collect(hwnd, _):
            if self.user32.IsWindowVisible(hwnd):
                window = self._window(hwnd)
                if window and window.title:
                    result.append(window)
            return len(result) < 128

        self.user32.EnumWindows(collect, 0)
        return tuple(result)

    @staticmethod
    def _speakers():
        from pycaw.pycaw import AudioUtilities

        return AudioUtilities.GetSpeakers()

    @staticmethod
    async def _manager():
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as Manager,
        )

        return await Manager.request_async()

    @staticmethod
    def _status(session) -> str:
        status = int(session.get_playback_info().playback_status)
        return {4: "playing", 5: "paused"}.get(status, "other")

    @staticmethod
    def _volume_sessions():
        from pycaw.pycaw import AudioUtilities

        return AudioUtilities.GetAllSessions()

    def _audio_sessions(self):
        self._audio_targets.clear()
        result = []
        for session in self._volume_sessions():
            try:
                if not session.ProcessId or int(session.State) == 2:
                    continue
                app = self._application(session.ProcessId)
                instance = session.InstanceIdentifier
                if not app.name or not instance:
                    continue
                ref = uuid4().hex
                self._audio_targets[ref] = (session.ProcessId, instance)
                result.append(
                    AudioSession(
                        id=ref,
                        app=app.name,
                        aliases=app.aliases,
                        level=round(session.SimpleAudioVolume.GetMasterVolume() * 100),
                    )
                )
            except Exception:
                continue
        return tuple(result)

    async def snapshot(self) -> DesktopContext:
        # Capture timestamp and foreground BEFORE async capability probes.
        captured_at = time.monotonic()
        self._applications.clear()
        foreground = self.foreground_id()
        windows = self.windows()
        unavailable = []
        device_id = volume = None
        try:
            device = self._speakers()
            device_id = device.id
            volume = round(device.EndpointVolume.GetMasterVolumeLevelScalar() * 100)
        except Exception:
            unavailable.append(
                "Systemlautstärke nicht verfügbar (Desktop-Extra/Ausgabegerät prüfen)"
            )
        audio = ()
        if device_id:
            try:
                audio = self._audio_sessions()
            except Exception:
                unavailable.append("App-Lautstärke nicht verfügbar")
        media = []
        self._media_targets.clear()
        try:
            manager = await asyncio.wait_for(self._manager(), timeout=3)
            sessions = list(manager.get_sessions())
            apps = [s.source_app_user_model_id for s in sessions]
            for session, app in zip(sessions, apps, strict=True):
                if apps.count(app) != 1:
                    unavailable.append(
                        "Mehrere Mediensitzungen derselben App: Ziel nicht eindeutig"
                    )
                    continue
                info = session.get_playback_info()
                ref = uuid4().hex
                media.append(
                    MediaSession(
                        id=ref,
                        app=app[:256],
                        status=self._status(session),
                        can_play=info.controls.is_play_enabled,
                        can_pause=info.controls.is_pause_enabled,
                        app_aliases=tuple(
                            dict.fromkeys(
                                alias
                                for window in windows
                                if window.process_name
                                and len(window.process_name.removesuffix(".exe")) >= 4
                                and window.process_name.casefold().removesuffix(".exe")
                                in app.casefold()
                                for alias in window.app_aliases
                            )
                        ),
                    )
                )
                self._media_targets[ref] = (app, session)
        except Exception:
            unavailable.append(
                "Gezielte Mediensteuerung nicht verfügbar (SMTC/Windows/Extra prüfen)"
            )
        context = DesktopContext(
            captured_at=captured_at,
            foreground_id=foreground,
            windows=windows,
            media_sessions=tuple(media),
            volume_device_id=device_id,
            volume=volume,
            audio_sessions=audio,
            unavailable=tuple(unavailable),
        )
        self._media_context_id = context.id
        self._audio_context_id = context.id
        return context

    def _check_foreground(self, context: DesktopContext, job: Job) -> None:
        job.check()
        if self.foreground_id() != context.foreground_id:
            raise PlatformError("Vordergrundfenster hat sich geändert; Auftrag bitte neu starten")

    async def execute(self, action: Action, context: DesktopContext, job: Job) -> ActionResult:
        self._check_foreground(context, job)
        try:
            if isinstance(action, FocusWindow):
                return await self._focus(action, context, job)
            if isinstance(action, LaunchApplication):
                return await self._launch_application(context, job)
            if isinstance(action, SetVolume):
                device = self._speakers()
                if device.id != action.device_id:
                    raise PlatformError("Standard-Audioausgabegerät hat sich geändert")
                self._check_foreground(context, job)
                device.EndpointVolume.SetMasterVolumeLevelScalar(action.level / 100, None)
                job.executed.append(action.type)
                job.state = State.VERIFYING
                actual = device.EndpointVolume.GetMasterVolumeLevelScalar() * 100
                same_device = self._speakers().id == action.device_id
                verified = same_device and abs(actual - action.level) <= 1
                return ActionResult(
                    verified=verified,
                    message=f"Systemlautstärke geprüft: {round(actual)} %"
                    if verified
                    else "Lautstärke wurde gesetzt; Ergebnis/Gerät konnte nicht bestätigt werden",
                )
            if isinstance(action, MediaControl):
                return await self._media(action, context, job)
            if isinstance(action, SetAppVolume):
                return self._set_app_volume(action, context, job)
            if isinstance(action, (UIElementAction, WriteText, BrowserKey, VisualClick)):
                return await self.ui.execute(action, context, job)
            raise PlatformError("Nicht unterstützte Windows-Aktion")
        except (ComputerFlowError, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise PlatformError(
                "Windows-Aktion fehlgeschlagen; keine automatische Wiederholung. "
                "Bereits ausgeführte Schritte werden im Status angezeigt."
            ) from exc

    async def _focus(self, action: FocusWindow, context: DesktopContext, job: Job) -> ActionResult:
        target = next((w for w in context.windows if w.id == action.window_id), None)
        if target is None:
            raise PlatformError("Fenster fehlt im Kontext")
        hwnd = int(target.id.split(":")[0], 16)
        current = self._window(hwnd)
        if current != target or not self.user32.IsWindowVisible(hwnd):
            raise PlatformError("Fensteridentität oder Fenstertitel hat sich geändert")
        self._check_foreground(context, job)
        if self.foreground_id() == target.id:
            return ActionResult(verified=True, message="Gewünschtes Fenster ist bereits aktiv")
        if self.user32.IsIconic(hwnd):
            self.user32.ShowWindowAsync(hwnd, 9)  # SW_RESTORE, non-blocking
            job.executed.append("restore_window")
            for _ in range(8):
                job.check()
                if self.foreground_id() == target.id:
                    return ActionResult(
                        verified=True, message="Fenster wiederhergestellt und aktiv"
                    )
                self._check_foreground(context, job)
                if not self.user32.IsIconic(hwnd):
                    break
                await asyncio.sleep(0.04)
            else:
                raise PlatformError("Fenster konnte nicht wiederhergestellt werden")
        self._check_foreground(context, job)
        job.check()
        accepted = self.user32.SetForegroundWindow(hwnd)
        job.executed.append(action.type)
        job.state = State.VERIFYING
        for _ in range(10):
            job.check()
            if self.foreground_id() == target.id:
                return ActionResult(verified=True, message="Fensterfokus geprüft")
            await asyncio.sleep(0.05)
        return ActionResult(
            verified=False,
            message="Fensterfokus nicht bestätigt; Windows kann den Fokuswechsel sperren"
            if not accepted
            else "Fensterfokus nach Aktion nicht bestätigt",
        )

    async def _launch_application(self, context, job):
        registration = context.launch_target

        def matches(window):
            if "!" in registration.id:
                return package_app_id(window.pid).casefold() == registration.id.casefold()
            return bool(matching_app_windows((window,), registration.name))

        before = {window.id for window in self.windows()}
        if any(matches(window) for window in self.windows()):
            raise PlatformError(
                "Die Anwendung ist inzwischen geöffnet. Bitte nenne den Auftrag erneut."
            )
        self.apps.launch(registration, job, lambda: self._check_foreground(context, job))
        job.executed.append("launch_application")
        job.state = State.VERIFYING
        deadline = time.monotonic() + 6
        attempted = False
        while time.monotonic() < deadline:
            job.check()
            foreground = self._window(self.user32.GetForegroundWindow())
            if foreground and foreground.id not in before and matches(foreground):
                return ActionResult(
                    verified=True,
                    message=f"{registration.name} geöffnet und aktiv",
                    foreground_id=foreground.id,
                )
            if foreground and foreground.id != context.foreground_id:
                raise PlatformError(
                    "Vordergrund hat sich beim Programmstart geändert. Auftrag angehalten."
                )
            if not attempted:
                launched = [
                    window
                    for window in self.windows()
                    if window.id not in before and matches(window)
                ]
                if len(launched) == 1:
                    job.check()
                    self.user32.SetForegroundWindow(int(launched[0].id.split(":", 1)[0], 16))
                    attempted = True
            await asyncio.sleep(0.1)
        return ActionResult(
            verified=False,
            message=f"Start von {registration.name} angefordert. Bitte aktiviere das Zielfenster.",
        )

    def _set_app_volume(self, action, context, job):
        identity = self._audio_targets.get(action.session_id)
        if (
            not identity
            or context.id != self._audio_context_id
            or self._speakers().id != context.volume_device_id
        ):
            raise PlatformError("App-Wiedergabesitzung oder Ausgabegerät hat sich geändert")
        matches = [
            s
            for s in self._volume_sessions()
            if (s.ProcessId, s.InstanceIdentifier) == identity and int(s.State) != 2
        ]
        if len(matches) != 1:
            raise PlatformError("App-Wiedergabesitzung ist nicht mehr eindeutig verfügbar")
        self._check_foreground(context, job)
        control = matches[0].SimpleAudioVolume
        control.SetMasterVolume(action.level / 100, None)
        job.executed.append(action.type)
        job.state = State.VERIFYING
        actual = control.GetMasterVolume() * 100
        okay = abs(actual - action.level) <= 0.6 and self._speakers().id == context.volume_device_id
        return ActionResult(
            verified=okay,
            message=f"App-Lautstärke geprüft: {round(actual)} %"
            if okay
            else "App-Lautstärke konnte nicht bestätigt werden",
        )

    async def _media(
        self,
        action: MediaControl,
        context: DesktopContext,
        job: Job,
    ) -> ActionResult:
        if context.id != self._media_context_id or action.session_id not in self._media_targets:
            raise PlatformError("Mediensitzung gehört nicht zum aktuellen Kontext")
        app, session = self._media_targets[action.session_id]
        manager = await job.guard(self._manager())
        matches = [s for s in manager.get_sessions() if s.source_app_user_model_id == app]
        if len(matches) != 1 or session.source_app_user_model_id != app:
            raise PlatformError("Mediensitzung ist nicht mehr eindeutig vorhanden")
        info = session.get_playback_info()
        desired = "playing" if action.operation == "play" else "paused"
        if self._status(session) == desired:
            return ActionResult(
                verified=True, message="Wiedergabe ist bereits im gewünschten Zustand"
            )
        if not getattr(info.controls, f"is_{action.operation}_enabled"):
            raise PlatformError("Mediensitzung erlaubt die Aktion nicht mehr")
        self._check_foreground(context, job)
        operation = getattr(session, f"try_{action.operation}_async")
        # The OS may already have received this request when cancellation arrives.
        job.executed.append(action.type)
        accepted = await job.guard(operation())
        job.state = State.VERIFYING
        for _ in range(20):
            job.check()
            if self._status(session) == desired:
                return ActionResult(verified=True, message=f"Wiedergabezustand geprüft: {desired}")
            if not accepted:
                break
            await asyncio.sleep(0.05)
        return ActionResult(
            verified=False,
            message="Medienaktion nicht bestätigt; keine automatische Wiederholung",
        )
