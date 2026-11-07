import asyncio
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace

from computerflow.actuator.executor import Confirmation, Executor
from computerflow.brain.contracts import InferenceBackend
from computerflow.brain.desktop import (
    bind_element,
    matching_app_windows,
    matching_surface_windows,
    matching_tabs,
)
from computerflow.brain.grounding import normalized_name
from computerflow.core.config import Config
from computerflow.core.contracts import (
    Act,
    Answer,
    Ask,
    FocusWindow,
    InspectUI,
    LaunchApplication,
    OpenApplication,
    Steps,
    Stop,
    UIElementAction,
    VisualClick,
)
from computerflow.core.errors import Cancelled, ComputerFlowError, PlatformError
from computerflow.core.jobs import Job, State
from computerflow.platform.contracts import DesktopPlatform


@dataclass(frozen=True)
class HistoryEntry:
    job_id: str
    state: State
    message: str
    executed: tuple[str, ...]
    elapsed_seconds: float


class Assistant:
    def __init__(
        self,
        config: Config,
        backend: InferenceBackend,
        platform: DesktopPlatform,
        status: Callable[[str], None] = print,
    ):
        self.config = config
        self.backend = backend
        self.platform = platform
        self.executor = Executor(platform, config.execution)
        self.status = status
        self.current: Job | None = None
        self.history: deque[HistoryEntry] = deque(maxlen=20)
        self._clarification: tuple[Ask, float] | None = None
        self._confirmation: Confirmation | None = None
        self._confirm_event = asyncio.Event()
        self.confirmation_started = 0.0

    async def _watch_context(self, context, job: Job) -> None:
        while job.state in {State.PLANNING, State.WAITING}:
            if not self.platform.context_is_current(context):
                self.status("Manueller Fensterwechsel erkannt; Auftrag wird unterbrochen")
                job.cancel()
                return
            await asyncio.sleep(0.05)

    def cancel(self) -> None:
        if self.current:
            self.current.cancel()
        self.executor.clear_confirmation()
        self._confirmation = None
        self._clarification = None
        self.status("Abbruch angefordert. Bereits gesendete Systemaktionen bleiben möglich.")

    def confirm(self) -> None:
        # Only the physical console/UI path can call this, never a model response.
        if self._confirmation is not None:
            self._confirm_event.set()

    @property
    def pending_confirmation(self):
        return self._confirmation

    def capture_at(self, stage: str, job: Job) -> None:
        config = self.config.vision
        if not config.enabled or config.timing not in {stage, "both"}:
            return
        capture = getattr(self.platform, "manual_capture", None)
        if capture:
            try:
                job.captures[stage] = capture()
            except (ComputerFlowError, ImportError, OSError) as exc:
                self.status(f"Bildkontext nicht verfügbar: {exc}")

    async def _ui_decision(self, request: InspectUI, context, job):
        if request.operation in {"tab", "stream"}:
            return await self._tab_decision(request, context, job)
        if request.operation == "chat" and request.source:
            windows = matching_surface_windows(context.windows, request.source)
            if all(w.id != context.foreground_id for w in windows):
                return Ask(
                    kind="ask",
                    question=(
                        f"Aktiviere den Chat von „{request.source}“ "
                        "und setze den Cursor ins Nachrichtenfeld."
                    ),
                ), context
        if request.window_id and request.window_id != context.foreground_id:
            raise PlatformError("Zielfenster hat sich geändert")
        if request.operation == "activate" and request.window:
            windows = matching_surface_windows(context.windows, request.window)
            if all(w.id != context.foreground_id for w in windows):
                return await self._tab_decision(request, context, job)
        inspect = getattr(self.platform, "inspect_ui", None)
        if not inspect or not context.foreground_id:
            return Ask(kind="ask", question="Welches Fenster soll ich bedienen?"), context
        ui = await job.guard(inspect(context.foreground_id, job))
        if (
            request.operation == "write"
            and not ui.protected_focus
            and not any(element.operation == "write" for element in ui.elements)
        ):
            # A restored window can publish its editing surface shortly after activation.
            await job.guard(asyncio.sleep(0.18))
            ui = await job.guard(inspect(context.foreground_id, job))
        context = context.model_copy(update={"ui": ui})
        bound = bind_element(request, context)
        if bound:
            return bound, context
        if request.operation in {"write", "chat"}:
            return Ask(
                kind="ask", question="Setze den Fokus in ein bearbeitbares Textfeld."
            ), context
        return await self._visual_decision(request, context, ui, job)

    async def _open_application(self, request, context, job):
        windows = matching_app_windows(context.windows, request.name)
        active = next((window for window in windows if window.id == context.foreground_id), None)
        if active or len(windows) == 1:
            return self._focus_action(context, (active or windows[0]).id), context
        if windows:
            return Ask(
                kind="ask", question=f"Welches Fenster von „{request.name}“ meinst du?"
            ), context
        catalog = getattr(self.platform, "registered_apps", None)
        apps = await job.guard(catalog(job)) if catalog else ()
        key = normalized_name(request.name)
        matches = [app for app in apps if normalized_name(app.name) == key]
        if len(matches) != 1:
            question = (
                f"Windows führt mehrere Apps als „{request.name}“. "
                "Wie heißt die gewünschte App im Startmenü?"
                if matches
                else f"Windows findet „{request.name}“ nicht als App. Wie heißt sie im Startmenü?"
            )
            return Ask(kind="ask", question=question), context
        app = matches[0]
        return Act(
            kind="act",
            action=LaunchApplication(
                type="launch_application",
                context_id=context.id,
                registration_id=app.id,
            ),
        ), context.model_copy(update={"launch_target": app})

    @staticmethod
    def _focus_action(context, window_id):
        return Act(
            kind="act",
            action=FocusWindow(type="focus_window", context_id=context.id, window_id=window_id),
        )

    async def _tab_decision(self, request, context, job):
        active = next((w for w in context.windows if w.id == context.foreground_id), None)
        scoped_click = request.operation == "activate"
        service = request.window if scoped_click else request.source
        source_windows = matching_surface_windows(context.windows, service) if service else []
        if request.window_id:
            windows = [active] if active and active.id == request.window_id else []
        elif request.window:
            windows = matching_surface_windows(context.windows, request.window)
        else:
            priority = [active] if active else []
            windows = list(
                {w.id: w for w in (*source_windows, *priority, *context.windows)}.values()
            )[:12]
        if scoped_click and not request.window_id:
            windows = list({w.id: w for w in (*source_windows, *context.windows)}.values())[:12]
        if not windows or len(windows) > 12:
            return Ask(
                kind="ask",
                question="Welches Fenster mit der gewünschten Registerkarte soll ich verwenden?",
                reply="tab",
            ), context
        inspect = getattr(self.platform, "inspect_tabs", None)
        observed = []
        if inspect:
            for window in windows:
                try:
                    observed.append(await job.guard(inspect(window.id, job)))
                except PlatformError:
                    continue
        matches = [] if scoped_click else matching_tabs(request, observed)
        if request.operation == "tab" and not request.window and not request.window_id:
            matches = [
                match for match in matches if match[0].window_id == context.foreground_id
            ] or matches
        if len(matches) > 1:
            return Ask(
                kind="ask",
                question=f"Mehrere Tabs passen zu „{request.value}“. Welchen Titel meinst du?",
                reply="tab",
            ), context
        if not matches and request.exact_tab:
            return Ask(
                kind="ask",
                question=f"Wie heißt der offene Tab „{request.value}“ genau?",
                reply="tab",
            ), context
        if not matches and service and active not in source_windows:
            source = InspectUI(kind="inspect_ui", operation="tab", value=service)
            service_tabs = matching_tabs(source, observed)
            if len(service_tabs) == 1:
                ui, element = service_tabs[0]
                followup = request.model_copy(update={"window_id": ui.window_id})
                if ui.window_id != context.foreground_id:
                    return Steps(
                        kind="steps", commands=(self._focus_action(context, ui.window_id), followup)
                    ), context
                return Steps(
                    kind="steps", commands=(self._select_tab(context, ui, element), followup)
                ), context.model_copy(update={"ui": ui})
            if len(source_windows) != 1 or request.window_id:
                return Ask(
                    kind="ask", question=f"Aktiviere das Fenster oder den Tab von „{service}“."
                ), context
        if matches:
            ui, element = matches[0]
            target = ui.window_id
        else:
            visible = source_windows or windows
            if request.operation == "tab" and request.window and active not in visible:
                tabbed = {ui.window_id for ui in observed if ui.elements}
                if len(tabbed) == 1:
                    visible = [window for window in visible if window.id in tabbed]
            target = (
                active.id if active in visible else visible[0].id if len(visible) == 1 else None
            )
            if target is None:
                return Ask(
                    kind="ask",
                    question="Aktiviere das Fenster mit der gewünschten Registerkarte.",
                    reply="tab",
                ), context
        if target != context.foreground_id:
            followup = request.model_copy(update={"window_id": target})
            return Steps(
                kind="steps", commands=(self._focus_action(context, target), followup)
            ), context
        if matches:
            return self._select_tab(context, ui, element), context.model_copy(update={"ui": ui})
        ui = next((candidate for candidate in observed if candidate.window_id == target), None)
        if (
            request.operation == "tab"
            and not request.window
            and not request.window_id
            and inspect
            and ui is None
        ):
            return Ask(
                kind="ask", question="In welcher App ist der gewünschte Tab geöffnet?", reply="tab"
            ), context
        return await self._visual_decision(request, context, ui, job)

    @staticmethod
    def _select_tab(context, ui, element):
        return Act(
            kind="act",
            action=UIElementAction(
                type="ui_element",
                context_id=context.id,
                window_id=ui.window_id,
                ui_id=ui.id,
                element_id=element.id,
            ),
        )

    async def _visual_decision(self, request, context, ui, job):
        if not self.config.vision.enabled:
            return Ask(
                kind="ask",
                question="Kein passendes Accessibility-Element. Die Bildaufnahme ist deaktiviert.",
            ), context
        capture = getattr(self.platform, "capture", None)
        if not capture:
            return Ask(
                kind="ask", question="Die Plattform liefert keinen Bildkontext für das Ziel."
            ), context
        at_cursor = request.operation == "cursor"
        snapshot = (
            None
            if at_cursor
            else next(
                (
                    screen
                    for screen in reversed(tuple(job.captures.values()))
                    if screen.window_id == context.foreground_id
                    and 0 <= time.monotonic() - screen.captured_at < 10
                ),
                None,
            )
        )
        if snapshot and not snapshot.marks and ui:
            snapshot = replace(
                snapshot,
                marks=tuple(
                    enumerate(
                        (
                            e
                            for e in ui.elements
                            if snapshot.crop.intersect(e.rect) and e.operation != "write"
                        ),
                        1,
                    )
                )[:35],
            )
        if snapshot is None:
            snapshot = capture(context.foreground_id, at_cursor=at_cursor, ui=ui)
        if at_cursor:
            point = snapshot.crop.normalized(*snapshot.cursor)
        else:
            locate = getattr(self.backend, "locate", None)
            label = request.value
            if request.operation == "tab":
                label = f"sichtbare Registerkarte „{request.value}“"
                locate = getattr(self.backend, "locate_tab", locate)
            elif request.operation == "stream":
                label = (
                    f"sichtbares Klickziel für den Stream „{request.value}“ auf „{request.source}“"
                )
            point = await job.guard(locate(label, snapshot, job)) if locate else None
        if point is None:
            if request.operation == "stream":
                question = f"In welchem Fenster ist der Stream „{request.value}“ sichtbar?"
            elif request.operation == "tab":
                question = f"Welche sichtbare Registerkarte meinst du mit „{request.value}“?"
            else:
                question = f"Wo ist „{request.value}“? Zeige darauf und sage „Klick hier“."
            return Ask(
                kind="ask",
                question=question,
                reply="tab" if request.operation == "tab" else None,
            ), context
        return Act(
            kind="act",
            action=VisualClick(
                type="visual_click",
                context_id=context.id,
                window_id=context.foreground_id,
                snapshot_id=snapshot.id,
                x=point[0],
                y=point[1],
                label=request.value,
                at_cursor=at_cursor,
            ),
        ), context.model_copy(update={"screen": snapshot})

    async def _planned(self, command, context, job, clarification):
        watcher = asyncio.create_task(self._watch_context(context, job))
        try:
            decision = (
                await job.guard(self.backend.plan(command, context, job, clarification))
                if isinstance(command, (str, bytes))
                else command
            )
            if isinstance(decision, InspectUI):
                return await self._ui_decision(decision, context, job)
            if isinstance(decision, OpenApplication):
                return await self._open_application(decision, context, job)
            return decision, context
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)

    def _describe(self, action, context):
        windows = {w.id: w for w in context.windows}
        target = windows.get(getattr(action, "window_id", None))
        window = (target.title or target.application) if target else "aktives Fenster"
        if action.type == "focus_window":
            return f"Wechsel zu {window}"
        if action.type == "launch_application":
            return f"Die registrierte App „{context.launch_target.name}“ öffnen"
        if action.type == "media_control":
            target = next(s for s in context.media_sessions if s.id == action.session_id)
            operation = "Wiedergabe starten" if action.operation == "play" else "pausieren"
            return f"{target.app} {operation}"
        if action.type == "set_volume":
            return f"Systemlautstärke auf {action.level} Prozent setzen"
        if action.type == "set_app_volume":
            target = next(s for s in context.audio_sessions if s.id == action.session_id)
            return f"Lautstärke von {target.app} auf {action.level} Prozent setzen"
        if action.type == "write_text":
            return f"In {window} den Text „{action.text}“ eingeben"
        if action.type == "ui_element":
            target = next(e for e in context.ui.elements if e.id == action.element_id)
            return f"In {window} {target.role} „{target.label}“ über Windows-Accessibility bedienen"
        if action.type == "visual_click":
            point = (
                context.screen.cursor
                if action.at_cursor
                else context.screen.crop.point(action.x, action.y)
            )
            return f"In {window} auf „{action.label}“ bei {point[0]}, {point[1]} klicken"
        return f"Browseraktion {action.key} in {window} ausführen"

    async def _approved(self, action, context, job, on_confirmation):
        if not self.executor.needs_confirmation(action, context):
            return None
        preview = getattr(self.platform, "preview_action", None)
        if isinstance(action, VisualClick) and preview:
            await job.guard(preview(action, context, job))
        if not self.platform.context_is_current(context):
            job.cancel()
            job.check()
        self._confirm_event.clear()
        confirmation = self.executor.request_confirmation(action, context, job)
        self._confirmation = confirmation
        self.confirmation_started = time.perf_counter()
        description = self._describe(action, context)
        mode = "Übungsfreigabe" if self.config.execution.practice_mode else "Freigabe"
        controls = (
            "F6 oder Computer, bestätigen"
            if self.config.execution.voice_confirmation and on_confirmation
            else "F6"
        )
        self.status(f"{mode} mit {controls}: {description}")
        if on_confirmation:
            on_confirmation(f"{description}. Drücke F6 für die Freigabe.")
        watcher = asyncio.create_task(self._watch_context(context, job))
        try:
            await job.guard(
                asyncio.wait_for(
                    self._confirm_event.wait(),
                    timeout=self.config.execution.confirmation_timeout_seconds,
                )
            )
        except TimeoutError:
            raise ComputerFlowError("Freigabe abgelaufen") from None
        finally:
            self._confirmation = None
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
        return confirmation

    async def _perform(self, decision, context, job, on_confirmation):
        job.check()
        if isinstance(decision, Act):
            self.executor.validate(decision.action, context, job)
            confirmation = await self._approved(decision.action, context, job, on_confirmation)
            if not self.platform.context_is_current(context):
                job.cancel()
                job.check()
            result = await self.executor.execute(decision.action, context, job, confirmation)
            expected = (
                decision.action.window_id
                if isinstance(decision.action, FocusWindow)
                else context.foreground_id
            )
            return result.message, result.foreground_id or expected
        if isinstance(decision, Ask):
            job.state = State.WAITING
            self._clarification = (decision, time.monotonic() + 60)
            return decision.question, None
        if isinstance(decision, Answer):
            job.state = State.DONE
            return decision.message, None
        if isinstance(decision, Stop):
            job.cancel()
            self._clarification = None
            return "Auftrag per Sprache/Text abgebrochen", None
        raise ComputerFlowError("Auftragsschritt konnte nicht eindeutig aufgelöst werden")

    async def run(
        self,
        command: str | bytes,
        job: Job | None = None,
        on_confirmation: Callable[[str], None] | None = None,
    ) -> HistoryEntry:
        if self.current is not None:
            raise ComputerFlowError("Ein Auftrag läuft bereits")
        job = job or Job(self.config.execution.timeout_seconds)
        self.current = job
        self._confirm_event.clear()
        self._confirmation = None
        message = ""
        try:
            job.check()
            job.state = State.PLANNING
            self.status(f"[{job.id[:8]}] {job.state}")
            context = await job.guard(self.platform.snapshot())
            for unavailable in context.unavailable:
                self.status(unavailable)
            clarification = None
            if self._clarification and time.monotonic() < self._clarification[1]:
                clarification = self._clarification[0]
            self._clarification = None
            decision, context = await self._planned(command, context, job, clarification)
            if isinstance(decision, Steps):
                pending = deque(decision.commands)
                index = 0
                while pending:
                    job.check()
                    job.state = State.PLANNING
                    step = pending.popleft()
                    item, current = await self._planned(step, context, job, None)
                    if isinstance(item, Steps):
                        if index + len(pending) + len(item.commands) > 3:
                            raise ComputerFlowError(
                                "Dieser Auftrag benötigt mehr als drei Schritte."
                            )
                        pending.extendleft(reversed(item.commands))
                        context = current
                        continue
                    index += 1
                    self.status(f"Schritt {index}/{index + len(pending)}")
                    message, expected = await self._perform(item, current, job, on_confirmation)
                    if job.state != State.DONE or not isinstance(item, Act) or not pending:
                        break
                    context = await job.guard(self.platform.snapshot())
                    if context.foreground_id != expected:
                        raise ComputerFlowError(
                            "Vordergrund hat sich geändert. Weitere Schritte wurden angehalten."
                        )
            else:
                message, _ = await self._perform(decision, context, job, on_confirmation)
        except Cancelled as exc:
            job.state = State.CANCELLED
            message = str(exc)
        except ComputerFlowError as exc:
            job.state = State.FAILED
            message = str(exc)
        except asyncio.CancelledError:
            job.cancel()
            message = "Auftrag abgebrochen"
            raise
        except Exception:
            job.state = State.FAILED
            message = "Unerwarteter Komponentenfehler; Auftrag sicher beendet"
        finally:
            job.captures.clear()
            entry = HistoryEntry(
                job_id=job.id,
                state=job.state,
                message=message,
                executed=tuple(job.executed),
                elapsed_seconds=round(time.monotonic() - job.started, 3),
            )
            self.history.append(entry)
            self.status(f"[{job.id[:8]}] {job.state}: {message}")
            if job.executed:
                self.status("Gesendete Schritte: " + ", ".join(job.executed))
            self.executor.clear_confirmation()
            self._confirmation = None
            self.current = None
        return entry
