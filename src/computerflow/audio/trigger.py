from collections.abc import Callable
from threading import Lock

from computerflow.core.config import ExecutionConfig, TriggerConfig
from computerflow.core.errors import ComputerFlowError


class KeyboardTrigger:
    """Only observes keys; no synthetic key events or held keys to clean up."""

    def __init__(
        self,
        config: TriggerConfig,
        execution: ExecutionConfig,
        start: Callable[[], None],
        finish: Callable[[], None],
        cancel: Callable[[], None],
        confirm: Callable[[], None],
    ):
        self.config = config
        self.execution = execution
        self.start = start
        self.finish = finish
        self.cancel = cancel
        self.confirm = confirm
        self._listener = None
        self._mouse_listener = None
        self._mouse_button = None
        self._pressed: set = set()
        self._active = False
        self._lock = Lock()

    def open(self) -> None:
        try:
            from pynput import keyboard

            self._keyboard = keyboard
            self._key = None
            if self.config.enabled:
                name = self.config.key
                if name.startswith("mouse:"):
                    from pynput import mouse

                    self._mouse_button = getattr(mouse.Button, name[6:])
                    self._mouse_listener = mouse.Listener(on_click=self._click)
                elif not (len(name) == 1 or name.startswith("vk:")):
                    self._key = getattr(keyboard.Key, name)
            self._listener = keyboard.Listener(on_press=self._press, on_release=self._release)
            self._listener.start()
            self._listener.wait()
            if self._mouse_listener:
                self._mouse_listener.start()
                self._mouse_listener.wait()
        except AttributeError as exc:
            self.close()
            raise ComputerFlowError(f"Unbekannte PTT-Taste: {self.config.key}") from exc
        except (ImportError, OSError, RuntimeError) as exc:
            self.close()
            raise ComputerFlowError("Globaler Tastatur-/Mauszugriff fehlt") from exc

    def _matches(self, key) -> bool:
        if not self.config.enabled or self.config.key.startswith("mouse:"):
            return False
        if self._key is not None:
            return key == self._key
        name = self.config.key
        if name.startswith("vk:"):
            return getattr(getattr(key, "value", key), "vk", None) == int(name[3:])
        return (getattr(key, "char", None) or "").casefold() == name

    def _press(self, key) -> None:
        if key in self._pressed:
            return
        self._pressed.add(key)
        k = self._keyboard.Key
        ctrl = bool(self._pressed & {k.ctrl, k.ctrl_l, k.ctrl_r})
        alt = bool(self._pressed & {k.alt, k.alt_l, k.alt_r, k.alt_gr})
        stop_key = k.esc if self.execution.emergency_hotkey.endswith("escape") else k.f12
        if ctrl and alt and stop_key in self._pressed:
            self.recording_finished()
            self.cancel()
        elif key == k.f6:
            self.confirm()
        elif self._matches(key):
            self._ptt(True)

    def _ptt(self, pressed: bool) -> None:
        with self._lock:
            if not pressed:
                if self._active and self.config.mode == "hold":
                    self._active = False
                    self.finish()
                return
            if self.config.mode == "toggle" and self._active:
                self._active = False
                self.finish()
            else:
                self._active = True
                self.start()

    def _release(self, key) -> None:
        self._pressed.discard(key)
        if self._matches(key):
            self._ptt(False)

    def _click(self, x, y, button, pressed, *args) -> None:
        if button == self._mouse_button:
            self._ptt(pressed)

    def recording_finished(self) -> None:
        with self._lock:
            self._active = False

    def close(self) -> None:
        for listener in (self._listener, self._mouse_listener):
            if listener is not None:
                listener.stop()
                if listener.ident is not None:
                    listener.join(timeout=2)
        self._listener = self._mouse_listener = None
        self._pressed.clear()
        self._active = False
