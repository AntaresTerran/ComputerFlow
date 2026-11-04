"""Temporarily lower other Windows audio sessions without changing channel levels."""

import math
import os
from contextlib import contextmanager


class Ducking:
    def __init__(self, percent: int, status):
        self.percent = percent
        self.status = status
        self._saved = []
        self._users = 0

    def begin(self) -> None:
        self._users += 1
        if not self.percent or self._users != 1:
            return
        try:
            from pycaw.pycaw import AudioUtilities

            for session in AudioUtilities.GetAllSessions():
                if not session.ProcessId or session.ProcessId == os.getpid():
                    continue
                try:
                    control = session.SimpleAudioVolume
                    level = control.GetMasterVolume()
                    lowered = level * (1 - self.percent / 100)
                    control.SetMasterVolume(lowered, None)
                    self._saved.append((control, level, lowered))
                except Exception:
                    self.status("Eine Wiedergabequelle konnte nicht abgesenkt werden")
        except Exception:
            self.status("Vorübergehende Lautstärkeabsenkung nicht verfügbar")

    def end(self) -> None:
        self._users = max(0, self._users - 1)
        if not self._users:
            self.restore()

    def restore(self) -> None:
        pending, self._saved = self._saved, []
        for control, level, lowered in pending:
            try:
                # A manual change during ducking takes precedence.
                if math.isclose(control.GetMasterVolume(), lowered, abs_tol=0.0001):
                    control.SetMasterVolume(level, None)
            except Exception:
                self.status("Eine abgesenkte Wiedergabequelle konnte nicht zurückgesetzt werden")
        self._users = 0

    @contextmanager
    def active(self):
        self.begin()
        try:
            yield
        finally:
            self.end()
