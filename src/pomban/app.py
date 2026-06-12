from __future__ import annotations

import contextlib
import time

from textual.app import App
from textual.binding import Binding

from pomban.core import config as cfg_module
from pomban.core import log
from pomban.core.config import Config
from pomban.core.config import save as save_config
from pomban.core.db import DB
from pomban.core.engine import PombanEngine, TickOutcome
from pomban.core.filter_state import FilterState
from pomban.core.filters import ProjectFilter
from pomban.core.models import Task
from pomban.core.session_coordinator import SessionCoordinator
from pomban.core.session_service import SessionService
from pomban.core.timer_engine import Event, Phase, Settings, TimerEngine
from pomban.notifications import NotifyConfig, fire, run_hook
from pomban.plugins import git_sync
from pomban.plugins import registry as plugin_registry
from pomban.screens.base import AppScreen
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.help import HelpScreen
from pomban.screens.history import HistoryScreen
from pomban.screens.kanban import KanbanScreen
from pomban.screens.presets import PresetPicker
from pomban.screens.resume import ResumePrompt
from pomban.screens.session_end import SessionEndScreen
from pomban.screens.stats import StatsScreen

THEMES = ["nord", "gruvbox", "dracula", "catppuccin-mocha"]


class PomodoroApp(App):
    SCREENS = {}  # registered in __init__ so we can pass per-instance state

    # Responsive: Textual auto-applies the class to each screen by width.
    # < 90 cols → "-narrow" (panes stack); >= 90 → "-wide".
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (90, "-wide")]

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("p", "pick_preset", "Preset", show=False),
        Binding("P,shift+p", "pick_project", "Project", show=False),
        Binding("L,shift+l", "lunch_break", "Lunch", show=False),
        Binding("F,shift+f", "pick_sprint", "Sprint", show=False),
        Binding("R,shift+r", "open_sprint_runner", "Sprint runner", show=False),
        Binding("T,shift+t", "toggle_auto_advance", "Auto-advance", show=False),
        Binding("b", "log_blocker", "Blocker", show=False),
    ]

    def __init__(
        self,
        db: DB | None = None,
        fast: bool = False,
        settings: Settings | None = None,
        notify_cfg: NotifyConfig | None = None,
        config: Config | None = None,
        config_path=None,
        first_run_check: bool | None = None,
    ) -> None:
        super().__init__()
        self.config = config or cfg_module.load(config_path)
        self.config_path = config_path
        # Default: only check on real launches. Tests pass ``fast=True`` for
        # quick timer settings on empty DBs, so suppress the modal there
        # unless the test explicitly opts in.
        self._first_run_check = (not fast) if first_run_check is None else first_run_check
        self.db = db or DB()
        self.sessions = SessionService(self.db)
        if settings is None:
            settings = (
                Settings(
                    focus_seconds=5,
                    short_break_seconds=3,
                    long_break_seconds=4,
                    cycles_before_long_break=4,
                    warning_seconds=2,
                )
                if fast
                else cfg_module.to_settings(self.config)
            )
        if notify_cfg is None:
            notify_cfg = cfg_module.to_notify_config(self.config)
        self.engine = TimerEngine(settings=settings)
        self.notify_cfg = notify_cfg
        self.coord = SessionCoordinator(self.engine, self.db, self.sessions)
        # PombanEngine facade owns the active-task set, wraps the timer / sessions
        # / coord, and exposes a UI-agnostic surface the app shell drives. Active
        # tasks live on the facade; app.py reads them via the shim properties below.
        # Filters persisted in config_kv: ui.active_project / ui.active_sprint
        self.filters = FilterState(self.db)
        self._facade = PombanEngine(
            db=self.db,
            sessions=self.sessions,
            coord=self.coord,
            timer=self.engine,
            plugin_registry=plugin_registry,
            hooks=self.config.hooks,
            run_hook=run_hook,
            filters=self.filters,
        )
        try:
            self._theme_idx = THEMES.index(self.config.ui.theme)
        except ValueError:
            self._theme_idx = 0
        self._pending_actual_seconds = 0

    # Multi-task focus state lives on the PombanEngine facade; the properties
    # below preserve the existing app.active_task* surface (used by screens and
    # tests) without duplicating the source of truth.
    @property
    def active_tasks(self) -> list[Task]:
        return self._facade.active_tasks

    @active_tasks.setter
    def active_tasks(self, tasks: list[Task]) -> None:
        self._facade.active_tasks = tasks

    @property
    def active_chip_index(self) -> int:
        return self._facade.active_chip_index

    @active_chip_index.setter
    def active_chip_index(self, idx: int) -> None:
        self._facade.active_chip_index = idx

    @property
    def active_task(self) -> Task | None:
        return self._facade.active_task

    @active_task.setter
    def active_task(self, task: Task | None) -> None:
        self._facade.active_task = task

    # Session bookkeeping lives in self.coord; expose the two fields as properties
    # so existing call sites (and tests) keep using app.current_session_id /
    # app.session_start_monotonic unchanged.
    @property
    def current_session_id(self) -> int | None:
        return self.coord.current_session_id

    @current_session_id.setter
    def current_session_id(self, value: int | None) -> None:
        self.coord.current_session_id = value

    @property
    def session_start_monotonic(self) -> float | None:
        return self.coord.session_start_monotonic

    @session_start_monotonic.setter
    def session_start_monotonic(self, value: float | None) -> None:
        self.coord.session_start_monotonic = value

    def on_mount(self) -> None:
        from pomban.screens.projects import ProjectsScreen
        from pomban.screens.sprints import SprintsScreen

        self.install_screen(DashboardScreen(), name="dashboard")
        self.install_screen(KanbanScreen(), name="kanban")
        self.install_screen(StatsScreen(), name="stats")
        self.install_screen(HistoryScreen(), name="history")
        self.install_screen(ProjectsScreen(), name="projects")
        self.install_screen(SprintsScreen(), name="sprints")
        self.push_screen("dashboard")
        plugin_registry().discover()
        self._maybe_prompt_resume()
        self._maybe_prompt_first_run()
        self.set_interval(0.25, self._tick)
        with contextlib.suppress(Exception):
            self.theme = THEMES[self._theme_idx]

    # ---------- ticking ----------
    def _tick(self) -> None:
        outcomes = self._facade.tick(time.monotonic())
        if outcomes:
            self._dispatch_outcomes(outcomes)
        self._refresh_active_screen_timer()

    def _dispatch_outcomes(self, outcomes: list[TickOutcome]) -> None:
        for o in outcomes:
            if o.kind == "ending_soon":
                self._on_ending_soon()
            elif o.kind == "phase_completed":
                self._on_phase_completed()

    def _refresh_active_screen_timer(self) -> None:
        try:
            scr = self.screen
        except Exception:
            return
        if isinstance(scr, AppScreen):
            try:
                scr.refresh_timer()
            except Exception:
                log.exception("refresh_timer failed on %s", type(scr).__name__)

    def _refresh_all(self) -> None:
        try:
            scr = self.screen
        except Exception:
            return
        if isinstance(scr, AppScreen):
            try:
                scr.refresh_view()
            except Exception:
                log.exception("refresh_view failed on %s", type(scr).__name__)

    def _handle_events(self, events: list[Event]) -> None:
        if Event.PHASE_ENDING_SOON in events:
            self._on_ending_soon()
        if Event.PHASE_COMPLETED in events:
            self._on_phase_completed()

    def _on_ending_soon(self) -> None:
        with contextlib.suppress(Exception):
            self.bell()
        with contextlib.suppress(Exception):
            self.notify(
                f"{self.engine.settings.warning_seconds}s left on {self.engine.phase.value}",
                timeout=3,
            )

    def _on_phase_completed(self) -> None:
        actual = 0
        if self.session_start_monotonic is not None:
            actual = int(time.monotonic() - self.session_start_monotonic)
        completed_phase = self.engine.phase
        task_title = self.active_task.title if self.active_task else None
        self._pending_actual_seconds = actual
        self._fire_phase_hooks(starting=False, phase=completed_phase)
        self._notify_phase_change(completed_phase)
        if self.config.timer.auto_advance:
            # Classic Pomodoro flow: advance straight to the next phase, no modal.
            # The session ended naturally (completed), but we do NOT mark the active
            # task(s) done — timer expiry isn't completion intent; they stay in Doing.
            sid_before_end = self.current_session_id
            self.coord.end(actual, completed=True)
            self._maybe_present_sprint_complete(sid_before_end)
            self.engine.confirm_advance(time.monotonic())
            self._log_new_session()
            self._refresh_all()
            return
        suggest_lunch = self._should_suggest_lunch(completed_phase)
        lunch_minutes = getattr(self.config, "breaks", None)
        lunch_minutes = lunch_minutes.lunch_minutes if lunch_minutes else 45
        multi_tasks = list(self.active_tasks) if len(self.active_tasks) > 1 else None
        screen = SessionEndScreen(
            completed_phase=completed_phase,
            task_title=task_title,
            suggest_lunch=suggest_lunch,
            lunch_minutes=lunch_minutes,
            multi_tasks=multi_tasks,
        )
        # Defer the modal push so the 0.25s tick callback returns immediately instead
        # of mounting a screen synchronously inside the timer loop. Capture the session
        # id now and guard the push: if a global action (e.g. Shift+L lunch, reset,
        # skip) changed the session in the gap before this runs, the modal is stale —
        # skip it so its callback can't end/mis-attribute the wrong session.
        sid_at_completion = self.current_session_id

        def _present_session_end() -> None:
            if self.current_session_id != sid_at_completion:
                return
            self.push_screen(screen, self._on_session_end_result)

        self.call_after_refresh(_present_session_end)
        self._refresh_active_screen_timer()

    def _should_suggest_lunch(self, completed_phase: Phase) -> bool:
        return self.coord.should_suggest_lunch(completed_phase, self.config)

    def _on_session_end_result(self, result: dict | None) -> None:
        actual = self._pending_actual_seconds
        sid = self.current_session_id
        if result is None:
            return
        action = result.get("action")
        if action == "extend":
            extra = int(result.get("seconds", 0))
            if sid is not None and extra > 0:
                self.sessions.extend_planned(sid, extra)
            self.engine.extend(extra, time.monotonic())
            self._refresh_all()
            return
        if action == "lunch":
            # Close the current session as completed (focus ended naturally) then start lunch.
            if sid is not None:
                self.sessions.end(sid, actual_seconds=actual, completed=True)
            self.current_session_id = None
            self.session_start_monotonic = None
            self.engine.confirm_advance(time.monotonic())  # advance state machine
            # Now drop into LONG_PAUSE.
            breaks = getattr(self.config, "breaks", None)
            minutes = breaks.lunch_minutes if breaks else 45
            self._start_long_pause(minutes * 60, label="lunch")
            return
        if action == "complete_multi":
            # Multi-task session: ask which of the active tasks are done.
            from pomban.screens.session_end import MultiCompleteModal

            tasks = list(self.active_tasks)
            self.push_screen(
                MultiCompleteModal(tasks),
                lambda ids: self._finalize_multi_complete(sid, actual, ids),
            )
            return
        completed_flag = action == "complete"
        if sid is not None:
            self.sessions.end(sid, actual_seconds=actual, completed=completed_flag)
        self.current_session_id = None
        self.session_start_monotonic = None
        if action == "complete" and self.active_task is not None:
            self.db.set_task_status(self.active_task.id, "done")
            self.active_task = None
        if completed_flag:
            self._maybe_present_sprint_complete(sid)
        self.engine.confirm_advance(time.monotonic())
        self._log_new_session()
        self._refresh_all()

    def _finalize_multi_complete(self, sid: int | None, actual: int, ids: list[int] | None) -> None:
        self._facade.finalize_multi_complete(sid, actual, ids)
        self._refresh_all()

    def _notify_phase_change(self, completed_phase: Phase) -> None:
        if completed_phase == Phase.FOCUS:
            title, body = "Focus done", "Mark task done or extend."
        elif completed_phase == Phase.SHORT_BREAK:
            title, body = "Break over", "Ready for the next focus."
        elif completed_phase == Phase.LONG_BREAK:
            title, body = "Long break over", "Ready for the next round."
        elif completed_phase == Phase.LONG_PAUSE:
            title, body = "Pause over", "Welcome back. Ready to focus?"
        else:
            return
        fire(title, body, self.notify_cfg)
        if self.notify_cfg.bell:
            try:
                self.bell()
                self.screen.styles.animate("opacity", 0.5, duration=0.1, on_complete=self._unflash)
            except Exception:
                pass

    def _unflash(self) -> None:
        with contextlib.suppress(Exception):
            self.screen.styles.animate("opacity", 1.0, duration=0.2)

    def _fire_phase_hooks(self, starting: bool, phase: Phase) -> None:
        self._facade.fire_phase_hooks(starting=starting, phase=phase)

    def _log_new_session(self) -> None:
        self._facade.log_new_session()

    # ---------- public API used by screens ----------
    def start_focus_on(self, task: Task) -> None:
        self.start_focus_on_many([task])

    def start_focus_on_many(self, tasks: list[Task]) -> None:
        """Start one focus session covering one or more tasks (Mode B)."""
        if not self._facade.start_focus_on_many(tasks):
            return
        # If we're on Kanban, jump to Dashboard so the timer is visible.
        if self.screen.__class__.__name__ != "DashboardScreen":
            with contextlib.suppress(Exception):
                self.switch_screen("dashboard")
        self._refresh_all()

    def submit_new_task(self, text: str, on_created=None) -> None:
        """Top-level entry for screen task-add inputs.

        If the text carries an explicit ``@project``, an active project filter
        is set, or an active sprint is set, the task is created synchronously
        (existing add_task_from_input path). Otherwise the project picker is
        pushed first; the task is created from the picker callback.
        """
        from pomban.core.task_input import parse_task_input

        parsed = parse_task_input(text)
        has_context = (
            bool(parsed.project_name)
            or self.project_filter.scoped_project_id is not None
            or self.active_sprint_id is not None
        )
        if has_context:
            task = self.add_task_from_input(text)
            self._announce_task_created(task)
            if on_created is not None:
                with contextlib.suppress(Exception):
                    on_created(task)
            self._refresh_all()
            return
        self._pending_task = (text, on_created)
        self.action_pick_project_for_task()

    def action_pick_project_for_task(self) -> None:
        from pomban.screens.project_picker import ProjectPickerModal

        self.push_screen(
            ProjectPickerModal(self.db.list_projects(), None),
            self._on_project_picked_for_task,
        )

    def _on_project_picked_for_task(self, result) -> None:
        pending = getattr(self, "_pending_task", None)
        self._pending_task = None
        if result is None or pending is None:
            return
        text, on_created = pending
        if result == -1 or result == 0:
            project_id = None
        else:
            project_id = int(result)
        from pomban.core.task_input import parse_task_input

        parsed = parse_task_input(text)
        sprint_id = None
        if parsed.sprint_name:
            sprint_id = self.db.get_or_create_sprint(project_id, parsed.sprint_name).id
        task = self.db.add_task(
            parsed.title,
            tags=parsed.tags_csv,
            estimated_pomodoros=parsed.estimate,
            project_id=project_id,
            sprint_id=sprint_id,
        )
        self._announce_task_created(task)
        if on_created is not None:
            with contextlib.suppress(Exception):
                on_created(task)
        self._refresh_all()

    def _announce_task_created(self, task: Task) -> None:
        if task.project_id is None:
            label = "Inbox"
        else:
            try:
                label = self.db.get_project(task.project_id).name
            except Exception:
                label = "project"
        with contextlib.suppress(Exception):
            self.notify(f"Created in {label}", timeout=2)

    def add_task_from_input(self, text: str) -> Task:
        """Create a task from the inline-metadata mini-syntax.

        Parsing lives in the pure ``core.task_input.parse_task_input``; this method
        resolves project/sprint names to ids and applies the active-filter defaults:
        a real project filter sets the project; the active sprint is inherited only
        when the user didn't type an explicit ``@project`` (the sprint is scoped to
        the filter project, so applying it elsewhere would be inconsistent).
        """
        from pomban.core.task_input import parse_task_input

        parsed = parse_task_input(text)
        project_id: int | None = None
        sprint_id: int | None = None
        if parsed.project_name:
            project_id = self.db.get_or_create_project(parsed.project_name).id
        elif self.project_filter.scoped_project_id is not None:
            project_id = self.project_filter.scoped_project_id
        if parsed.sprint_name:
            sprint_id = self.db.get_or_create_sprint(project_id, parsed.sprint_name).id
        elif self.active_sprint_id is not None and not parsed.project_name:
            sprint_id = self.active_sprint_id
        return self.db.add_task(
            parsed.title,
            tags=parsed.tags_csv,
            estimated_pomodoros=parsed.estimate,
            project_id=project_id,
            sprint_id=sprint_id,
        )

    def delete_task_by_id(self, task_id: int) -> None:
        self.active_tasks = [t for t in self.active_tasks if t.id != task_id]
        self.db.delete_task(task_id)

    # ---------- global actions ----------
    def action_switch(self, name: str) -> None:
        valid = ["dashboard", "kanban", "stats", "history", "projects", "sprints"]
        if name in valid:
            try:
                self.switch_screen(name)
            except Exception:
                log.exception("switch_screen failed for %s", name)
                return
            scr = self.screen
            if isinstance(scr, AppScreen):
                try:
                    scr.refresh_view()
                except Exception:
                    log.exception("refresh_view failed on %s", type(scr).__name__)

    def action_toggle(self) -> None:
        was_idle = self.engine.phase == Phase.IDLE
        was_running_focus = self.engine.running and self.engine.phase == Phase.FOCUS
        events = self.engine.toggle(time.monotonic())
        if was_idle and self.engine.phase == Phase.FOCUS:
            self._log_new_session()
        elif was_running_focus and not self.engine.running and self.current_session_id is not None:
            # User paused mid-focus — log as an interruption.
            self.sessions.log_interruption(self.current_session_id)
        self._handle_events(events)
        self._refresh_all()

    def action_reset(self) -> None:
        if self.current_session_id is not None and self.session_start_monotonic is not None:
            self.coord.end(self.coord.elapsed(), completed=False)
        self.engine.reset()
        self._refresh_all()

    def action_skip(self) -> None:
        events = self.engine.skip(time.monotonic())
        if Event.PHASE_COMPLETED in events and self.current_session_id is not None:
            self.coord.end(self.coord.elapsed(), completed=False)
            self._log_new_session()
        self._refresh_all()

    def action_start_on_selected(self) -> None:
        scr = self.screen
        sel = getattr(scr, "selected_task", lambda: None)()
        if sel:
            self.start_focus_on(sel)

    def action_delete_task(self) -> None:
        scr = self.screen
        sel = getattr(scr, "selected_task", lambda: None)()
        if sel:
            self.delete_task_by_id(sel.id)
            self._refresh_all()

    def action_complete_task(self) -> None:
        scr = self.screen
        sel = getattr(scr, "selected_task", lambda: None)()
        if sel:
            self.db.set_task_status(sel.id, "done")
            self.active_tasks = [t for t in self.active_tasks if t.id != sel.id]
            self._refresh_all()

    def _focused_task(self) -> Task | None:
        """Resolve the task the user is pointing at on the current screen."""
        scr = self.screen
        sel = getattr(scr, "selected_task", None)
        if callable(sel):
            t = sel()
            if t is not None:
                return t
        card = getattr(scr, "focused_card", None)
        if callable(card):
            c = card()
            if c is not None:
                return getattr(c, "task_data", None)
        return None

    def action_edit_task(self) -> None:
        task = self._focused_task()
        if task is None:
            return
        from pomban.screens.edit_task import EditTaskModal

        project_name = None
        if task.project_id is not None:
            try:
                project_name = self.db.get_project(task.project_id).name
            except Exception:
                log.exception("loading project %s for edit failed", task.project_id)
                project_name = None
        self.push_screen(
            EditTaskModal(task, project_name=project_name),
            lambda result: self._on_task_edited(task.id, result),
        )

    def _on_task_edited(self, task_id: int, result: dict | None) -> None:
        if result is None:
            return
        project_name = (result.get("project") or "").strip()
        project_id = self.db.get_or_create_project(project_name).id if project_name else None
        self.db.update_task(
            task_id,
            title=result["title"],
            tags=result["tags"],
            estimated_pomodoros=result["estimate"],
            project_id=project_id,
            due_date=result.get("due_date", ""),
            priority=result.get("priority", 0),
        )
        self._refresh_all()

    def action_help(self) -> None:
        # Snapshot the live, context-aware bindings (app + screen + focused widget)
        # so the overlay always matches reality and reflects the focused panel.
        snapshot: list[tuple[str, str]] = []
        seen: set[str] = set()
        try:
            for ab in self.screen.active_bindings.values():
                b = ab.binding
                if b.description and b.description not in seen:
                    seen.add(b.description)
                    snapshot.append((b.key, b.description))
        except Exception:
            log.exception("failed to snapshot bindings for help")
        self.push_screen(HelpScreen(snapshot))

    def _maybe_prompt_first_run(self) -> None:
        """Empty-DB launch: push FirstRunModal to seed an initial project."""
        if not self._first_run_check:
            return
        if not self._facade.is_first_run():
            return
        from pomban.screens.first_run import FirstRunModal

        self.push_screen(FirstRunModal(), self._on_first_run_result)

    def _on_first_run_result(self, name: str | None) -> None:
        if not name:
            return
        try:
            project = self.db.get_or_create_project(name)
        except Exception:
            log.exception("first-run project creation failed for %r", name)
            return
        self.set_active_project(project.id)
        with contextlib.suppress(Exception):
            self.notify(f"Project '{project.name}' created", timeout=3)

    def _maybe_prompt_resume(self) -> None:
        pending = self.db.kv_get("pending_session_id")
        if not pending:
            return
        try:
            sid = int(pending)
        except ValueError:
            self.db.kv_delete("pending_session_id")
            return
        remaining = int(self.db.kv_get("pending_remaining_seconds") or 0)
        phase_str = self.db.kv_get("pending_phase") or "focus"
        task_id_str = self.db.kv_get("pending_task_id")
        task_title = None
        if task_id_str:
            try:
                task_title = self.db.get_task(int(task_id_str)).title
            except Exception:
                log.exception("loading pending task %s for resume failed", task_id_str)
                task_title = None
        self.push_screen(
            ResumePrompt(task_title, remaining),
            lambda resume: self._on_resume_choice(resume, sid, remaining, phase_str, task_id_str),
        )

    def _on_resume_choice(
        self, resume: bool | None, sid: int, remaining: int, phase_str: str, task_id_str: str | None
    ) -> None:
        for k in (
            "pending_session_id",
            "pending_remaining_seconds",
            "pending_phase",
            "pending_task_id",
        ):
            self.db.kv_delete(k)
        if not resume:
            with contextlib.suppress(Exception):
                self.sessions.end(sid, actual_seconds=0, completed=False)
            return
        # Resume: load task, restore engine state, log nothing new (reuse session row).
        if task_id_str:
            try:
                self.active_task = self.db.get_task(int(task_id_str))
            except Exception:
                log.exception("restoring active task %s on resume failed", task_id_str)
                self.active_task = None
        self.engine.restore(Phase(phase_str), remaining, running=True, now=time.monotonic())
        self.current_session_id = sid
        self.session_start_monotonic = time.monotonic()
        self._refresh_all()

    def _persist_pending_session(self) -> None:
        if self.current_session_id is None or self.engine.phase == Phase.IDLE:
            return
        # Capture latest remaining via a tick.
        self.engine.tick(time.monotonic())
        self.db.kv_set("pending_session_id", str(self.current_session_id))
        self.db.kv_set("pending_remaining_seconds", str(self.engine.remaining))
        self.db.kv_set("pending_phase", self.engine.phase.value)
        if self.active_task:
            self.db.kv_set("pending_task_id", str(self.active_task.id))

    async def on_unmount(self) -> None:
        self._persist_pending_session()
        if self.config.sync.enabled:
            try:
                git_sync(self.db.path.parent)
            except Exception:
                log.exception("git_sync on shutdown failed")

    def action_pick_preset(self) -> None:
        if not self.config.presets:
            with contextlib.suppress(Exception):
                self.notify(
                    "No presets configured. Add [[preset]] entries to your config.toml.", timeout=4
                )
            return
        self.push_screen(PresetPicker(self.config.presets), self._on_preset_picked)

    def _on_preset_picked(self, preset) -> None:
        if preset is None:
            return
        self.engine.settings = Settings(
            focus_seconds=preset.focus_minutes * 60,
            short_break_seconds=preset.short_break_minutes * 60,
            long_break_seconds=preset.long_break_minutes * 60,
            cycles_before_long_break=preset.cycles_before_long_break,
            warning_seconds=self.engine.settings.warning_seconds,
        )
        with contextlib.suppress(Exception):
            self.notify(f"Preset '{preset.name}' will apply on next session.", timeout=3)

    # ---------- project / sprint filter (state lives in self.filters) ----------
    @property
    def project_filter(self) -> ProjectFilter:
        return self.filters.project

    @property
    def active_sprint_id(self) -> int | None:
        return self.filters.sprint_id

    @active_sprint_id.setter
    def active_sprint_id(self, value: int | None) -> None:
        # Direct assignment sets state without persisting (used by tests / internal
        # paths); use set_active_sprint() to persist + refresh.
        self.filters.sprint_id = value

    def set_project_filter(self, pf: ProjectFilter) -> None:
        self.filters.set_project(pf)
        self._refresh_all()

    def set_active_project(self, project_id: int | None) -> None:
        """Convenience: filter to a specific project, or All when None."""
        self.set_project_filter(
            ProjectFilter.all() if project_id is None else ProjectFilter.project(project_id)
        )

    def set_active_sprint(self, sprint_id: int | None) -> None:
        self.filters.set_sprint(sprint_id)
        self._refresh_all()

    def action_pick_project(self) -> None:
        from pomban.screens.project_picker import ProjectPickerModal

        self.push_screen(
            ProjectPickerModal(self.db.list_projects(), self.project_filter.project_id),
            self._on_project_picked,
        )

    def _on_project_picked(self, result) -> None:
        if result is None:
            return
        # result is either int (project id), 0 (Inbox), or -1 (All)
        if result == -1:
            self.set_project_filter(ProjectFilter.all())
            label = "All"
        elif result == 0:
            self.set_project_filter(ProjectFilter.inbox())
            label = "Inbox"
        else:
            self.set_project_filter(ProjectFilter.project(int(result)))
            try:
                label = self.db.get_project(int(result)).name
            except Exception:
                log.exception("loading project %s for picker label failed", result)
                label = "project"
        with contextlib.suppress(Exception):
            self.notify(f"Project filter: {label}", timeout=2)

    def action_cycle_project(self) -> None:
        """Cycle through: All → each project → Inbox → All ..."""
        projects = self.db.list_projects()
        cycle = (
            [ProjectFilter.all()]
            + [ProjectFilter.project(p.id) for p in projects]
            + [ProjectFilter.inbox()]
        )
        try:
            idx = cycle.index(self.project_filter)
        except ValueError:
            idx = 0
        nxt = cycle[(idx + 1) % len(cycle)]
        self.set_project_filter(nxt)
        label = self.active_project_label() or "All"
        with contextlib.suppress(Exception):
            self.notify(f"Project: {label}", timeout=2)

    def project_filter_for_db(self):
        """Translate the active filter into the db.list_tasks `project_filter` value."""
        return self.filters.for_db()

    def active_project_label(self) -> str | None:
        return self.filters.project_label()

    def active_project_color(self) -> str:
        return self.filters.project_color()

    def _maybe_present_sprint_complete(self, session_id: int | None) -> None:
        """Push SprintCompleteModal iff the just-ended session crossed the target."""
        sprint = self._facade.check_sprint_target_hit(session_id)
        if sprint is None:
            return
        from pomban.screens.sprint_complete import SprintCompleteModal

        progress = self.db.sprint_progress(sprint.id)
        modal = SprintCompleteModal(
            sprint_name=sprint.name,
            completed=progress["completed"],
            target=progress["target"],
        )

        def _present() -> None:
            self.push_screen(modal, lambda choice: self._on_sprint_complete(sprint.id, choice))

        # Deferred so we never push from inside a tick callback.
        self.call_after_refresh(_present)

    def _on_sprint_complete(self, sprint_id: int, choice: str | None) -> None:
        if choice != "close_retro":
            return
        from pomban.screens.sprint_runner import RetroModal

        try:
            sp = self.db.get_sprint(sprint_id)
            initial = sp.retrospective or ""
        except Exception:
            log.exception("loading sprint %s for retro failed", sprint_id)
            initial = ""
        self.push_screen(
            RetroModal("Sprint retrospective", initial=initial),
            lambda retro: self._on_post_complete_retro(sprint_id, retro),
        )

    def _on_post_complete_retro(self, sprint_id: int, retro: str | None) -> None:
        if retro is None:
            return
        self._facade.close_sprint(sprint_id, retro)
        self.set_active_sprint(None)
        with contextlib.suppress(Exception):
            self.notify("Sprint closed.", timeout=2)

    def action_log_blocker(self) -> None:
        """Push BlockerModal mid-focus to log an interruption on the active session."""
        sid = self.current_session_id
        if self.engine.phase != Phase.FOCUS or sid is None:
            with contextlib.suppress(Exception):
                self.notify("No focus session active.", timeout=2)
            return
        from pomban.screens.blocker import BlockerModal

        self.push_screen(BlockerModal(), lambda reason: self._on_blocker_result(sid, reason))

    def _on_blocker_result(self, session_id: int, reason: str | None) -> None:
        if reason is None:
            return
        try:
            self.sessions.log_interruption(session_id, reason=reason)
        except Exception:
            log.exception("log_interruption failed for session %s", session_id)
            return
        self._refresh_all()
        with contextlib.suppress(Exception):
            self.notify(f"⚠ Blocker logged{(': ' + reason) if reason else ''}", timeout=2)

    def action_open_sprint_runner(self) -> None:
        """Push :class:`SprintRunnerScreen` when an active sprint exists."""
        if self._facade.active_sprint_progress() is None:
            with contextlib.suppress(Exception):
                self.notify("No active sprint. Pick one with Shift+F.", timeout=3)
            return
        from pomban.screens.sprint_runner import SprintRunnerScreen

        self.push_screen(SprintRunnerScreen())

    def action_pick_sprint(self) -> None:
        from pomban.screens.sprint_picker import SprintPickerModal

        # Sprints scoped to the active project (or all if no real project filter)
        scope_pid = self.project_filter.scoped_project_id
        sprints = self.db.list_sprints(project_id=scope_pid)
        self.push_screen(
            SprintPickerModal(sprints, self.active_sprint_id),
            self._on_sprint_picked,
        )

    def _on_sprint_picked(self, result) -> None:
        if result is None:
            return
        if result == -1:
            self.set_active_sprint(None)
            return
        self.set_active_sprint(int(result))

    # ---------- lunch break ----------
    def action_lunch_break(self) -> None:
        """Start a long pause (lunch). Saves current phase to resume after."""
        breaks = getattr(self.config, "breaks", None)
        minutes = breaks.lunch_minutes if breaks else 45
        self._start_long_pause(minutes * 60, label="lunch")

    def _start_long_pause(self, seconds: int, label: str = "long_pause") -> None:
        # If a session is running, log an interruption with reason, end it as incomplete.
        if self.current_session_id is not None and self.session_start_monotonic is not None:
            try:
                self.sessions.log_interruption(self.current_session_id, reason=label)
            except Exception:
                log.exception("log_interruption failed for session %s", self.current_session_id)
            self.coord.end(self.coord.elapsed(), completed=False)
        # Remember the phase we interrupted so the engine resumes it after the pause.
        prev_phase = self.engine.phase
        self.engine.enter_long_pause(seconds, time.monotonic(), resume_phase=prev_phase)
        # Log the long pause as a session (engine is now in LONG_PAUSE with
        # remaining == seconds, so coord.begin records the right planned time).
        self.coord.begin([])
        with contextlib.suppress(Exception):
            self.notify(f"⏸  {label} started ({seconds // 60} min)", timeout=3)
        self._refresh_all()

    def action_toggle_auto_advance(self) -> None:
        self.config.timer.auto_advance = not self.config.timer.auto_advance
        state = "on" if self.config.timer.auto_advance else "off"
        with contextlib.suppress(Exception):
            self.notify(f"Auto-advance {state}", timeout=2)
        if self.config_path is not None:
            try:
                save_config(self.config, self.config_path)
            except Exception:
                log.exception("persisting auto_advance toggle failed")

    def action_cycle_theme(self) -> None:
        self._theme_idx = (self._theme_idx + 1) % len(THEMES)
        name = THEMES[self._theme_idx]
        with contextlib.suppress(Exception):
            self.theme = name
        self.config.ui.theme = name
        if self.config_path is not None:
            try:
                save_config(self.config, self.config_path)
            except Exception:
                log.exception("persisting theme change failed")
