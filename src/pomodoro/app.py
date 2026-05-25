from __future__ import annotations

import time

from textual.app import App
from textual.binding import Binding

from pomodoro.core import config as cfg_module
from pomodoro.core.config import Config, save as save_config
from pomodoro.core import log
from pomodoro.core.db import DB
from pomodoro.core.filters import ProjectFilter
from pomodoro.core.models import Task
from pomodoro.core.session_service import SessionService
from pomodoro.core.timer_engine import Event, Phase, Settings, TimerEngine
from pomodoro.music import MusicController
from pomodoro.notifications import NotifyConfig, fire, run_hook
from pomodoro.plugins import git_sync, registry as plugin_registry
from pomodoro.screens.base import AppScreen
from pomodoro.screens.presets import PresetPicker
from pomodoro.screens.resume import ResumePrompt
from pomodoro.screens.dashboard import DashboardScreen
from pomodoro.screens.help import HelpScreen
from pomodoro.screens.history import HistoryScreen
from pomodoro.screens.kanban import KanbanScreen
from pomodoro.screens.session_end import SessionEndScreen
from pomodoro.screens.stats import StatsScreen
from pomodoro.widgets.stats_strip import StatsStrip
from pomodoro.widgets.timer_display import TimerDisplay


THEMES = ["nord", "gruvbox", "dracula", "catppuccin-mocha"]


class PomodoroApp(App):
    SCREENS = {}  # registered in __init__ so we can pass per-instance state

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("p", "pick_preset", "Preset", show=False),
        Binding("P,shift+p", "pick_project", "Project", show=False),
        Binding("L,shift+l", "lunch_break", "Lunch", show=False),
        Binding("F,shift+f", "pick_sprint", "Sprint", show=False),
        Binding("T,shift+t", "toggle_auto_advance", "Auto-advance", show=False),
        Binding("m", "music_toggle", "Music", show=False),
        Binding("M,shift+m", "music_next", "Next track", show=False),
    ]

    def __init__(self, db: DB | None = None, fast: bool = False, settings: Settings | None = None,
                 notify_cfg: NotifyConfig | None = None, config: Config | None = None,
                 config_path=None) -> None:
        super().__init__()
        self.config = config or cfg_module.load(config_path)
        self.config_path = config_path
        self.db = db or DB()
        self.sessions = SessionService(self.db)
        if settings is None:
            settings = (Settings(focus_seconds=5, short_break_seconds=3, long_break_seconds=4,
                                 cycles_before_long_break=4, warning_seconds=2)
                        if fast else cfg_module.to_settings(self.config))
        if notify_cfg is None:
            notify_cfg = cfg_module.to_notify_config(self.config)
        self.engine = TimerEngine(settings=settings)
        self.notify_cfg = notify_cfg
        self.music = MusicController(self.config.music)
        # Multi-task focus: active_tasks is the source of truth; active_task is a
        # back-compat property (active_tasks[0]). active_chip_index drives the
        # cosmetic chip highlight on the Dashboard timer.
        self.active_tasks: list[Task] = []
        self.active_chip_index: int = 0
        self.current_session_id: int | None = None
        self.session_start_monotonic: float | None = None
        # Filters persisted in config_kv: ui.active_project / ui.active_sprint
        self.project_filter = ProjectFilter.from_kv(self.db.kv_get("ui.active_project"))
        self.active_sprint_id: int | None = self._load_filter("ui.active_sprint")
        try:
            self._theme_idx = THEMES.index(self.config.ui.theme)
        except ValueError:
            self._theme_idx = 0
        self._pending_actual_seconds = 0

    @property
    def active_task(self) -> Task | None:
        return self.active_tasks[0] if self.active_tasks else None

    @active_task.setter
    def active_task(self, task: Task | None) -> None:
        self.active_tasks = [task] if task else []

    def on_mount(self) -> None:
        from pomodoro.screens.projects import ProjectsScreen
        from pomodoro.screens.sprints import SprintsScreen
        self.install_screen(DashboardScreen(), name="dashboard")
        self.install_screen(KanbanScreen(), name="kanban")
        self.install_screen(StatsScreen(), name="stats")
        self.install_screen(HistoryScreen(), name="history")
        self.install_screen(ProjectsScreen(), name="projects")
        self.install_screen(SprintsScreen(), name="sprints")
        self.push_screen("dashboard")
        plugin_registry().discover()
        self._maybe_prompt_resume()
        self.set_interval(0.25, self._tick)
        # Auto-start a headless music daemon (off-thread so it can't block launch),
        # so the music panel works without a separately-launched player instance.
        if self.config.music.enabled:
            self.run_worker(self.music.start_daemon, thread=True, group="music-daemon")
        try:
            self.theme = THEMES[self._theme_idx]
        except Exception:
            pass

    # ---------- ticking ----------
    def _tick(self) -> None:
        if not self.engine.running:
            return
        events = self.engine.tick(time.monotonic())
        if events:
            self._handle_events(events)
        self._refresh_active_screen_timer()

    def _refresh_active_screen_timer(self) -> None:
        try:
            scr = self.screen
        except Exception:
            return
        if hasattr(scr, "refresh_timer"):
            try:
                scr.refresh_timer()
            except Exception:
                pass

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
        try:
            self.bell()
        except Exception:
            pass
        try:
            self.notify(
                f"{self.engine.settings.warning_seconds}s left on {self.engine.phase.value}",
                timeout=3,
            )
        except Exception:
            pass

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
            sid = self.current_session_id
            if sid is not None:
                self.sessions.end(sid, actual_seconds=actual, completed=True)
            self.current_session_id = None
            self.session_start_monotonic = None
            self.engine.confirm_advance(time.monotonic())
            self._log_new_session()
            self._refresh_all()
            return
        suggest_lunch = self._should_suggest_lunch(completed_phase)
        lunch_minutes = getattr(self.config, "breaks", None)
        lunch_minutes = lunch_minutes.lunch_minutes if lunch_minutes else 45
        multi_tasks = list(self.active_tasks) if len(self.active_tasks) > 1 else None
        screen = SessionEndScreen(completed_phase=completed_phase, task_title=task_title,
                                  suggest_lunch=suggest_lunch, lunch_minutes=lunch_minutes,
                                  multi_tasks=multi_tasks)
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
        if completed_phase != Phase.FOCUS:
            return False
        breaks = getattr(self.config, "breaks", None)
        if breaks is None:
            return False
        if not breaks.lunch_window_start or not breaks.lunch_window_end:
            return False
        from datetime import datetime
        try:
            now = datetime.now().time()
            start_h, start_m = (int(x) for x in breaks.lunch_window_start.split(":"))
            end_h, end_m = (int(x) for x in breaks.lunch_window_end.split(":"))
        except Exception:
            return False
        start = (start_h, start_m)
        end = (end_h, end_m)
        cur = (now.hour, now.minute)
        if not (start <= cur <= end):
            return False
        # Was lunch already taken today? (cached — keeps this off the tick path)
        return not self.sessions.lunch_taken_today()

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
            self.engine.confirm_advance(time.monotonic())   # advance state machine
            # Now drop into LONG_PAUSE.
            breaks = getattr(self.config, "breaks", None)
            minutes = breaks.lunch_minutes if breaks else 45
            self._start_long_pause(minutes * 60, label="lunch")
            return
        if action == "complete_multi":
            # Multi-task session: ask which of the active tasks are done.
            from pomodoro.screens.session_end import MultiCompleteModal
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
        self.engine.confirm_advance(time.monotonic())
        self._log_new_session()
        self._refresh_all()

    def _finalize_multi_complete(self, sid: int | None, actual: int,
                                 ids: list[int] | None) -> None:
        ids = ids or []
        if sid is not None:
            self.sessions.end(sid, actual_seconds=actual, completed=True)
        self.current_session_id = None
        self.session_start_monotonic = None
        done = set(ids)
        for tid in done:
            self.db.set_task_status(tid, "done")
        # Completed tasks leave the active set; the rest stay in Doing.
        self.active_tasks = [t for t in self.active_tasks if t.id not in done]
        self.engine.confirm_advance(time.monotonic())
        self._log_new_session()
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
        try:
            self.screen.styles.animate("opacity", 1.0, duration=0.2)
        except Exception:
            pass

    def _fire_phase_hooks(self, starting: bool, phase: Phase) -> None:
        hooks = self.config.hooks
        task_title = self.active_task.title if self.active_task else ""
        env = {
            "POMODORO_PHASE": phase.value,
            "POMODORO_TASK_TITLE": task_title,
            "POMODORO_EVENT": "start" if starting else "end",
        }
        if phase == Phase.FOCUS:
            cmd = hooks.on_focus_start if starting else hooks.on_focus_end
        else:
            cmd = hooks.on_break_start if starting else hooks.on_break_end
        run_hook(cmd, env)
        # In-process plugins (F19)
        reg = plugin_registry()
        if starting:
            reg.fire("on_phase_started", phase.value, task_title or None)
        else:
            reg.fire("on_phase_completed", phase.value, task_title or None, True)
        # Music: focus drives focus_*, every other phase (incl. LONG_PAUSE/lunch)
        # drives break_* so playback pauses during breaks and lunch.
        kind = "focus" if phase == Phase.FOCUS else "break"
        self.music.fire(f"{kind}_{'start' if starting else 'end'}")

    def _log_new_session(self) -> None:
        if self.engine.phase == Phase.IDLE:
            return
        self._fire_phase_hooks(starting=True, phase=self.engine.phase)
        task_ids = (
            [t.id for t in self.active_tasks]
            if self.engine.phase == Phase.FOCUS
            else []
        )
        planned = {
            Phase.FOCUS: self.engine.settings.focus_seconds,
            Phase.SHORT_BREAK: self.engine.settings.short_break_seconds,
            Phase.LONG_BREAK: self.engine.settings.long_break_seconds,
            Phase.LONG_PAUSE: self.engine.remaining or 45 * 60,
        }.get(self.engine.phase, 0)
        self.current_session_id = self.sessions.start(
            self.engine.phase.value, planned, task_ids
        )
        self.session_start_monotonic = time.monotonic()

    # ---------- public API used by screens ----------
    def start_focus_on(self, task: Task) -> None:
        self.start_focus_on_many([task])

    def start_focus_on_many(self, tasks: list[Task]) -> None:
        """Start one focus session covering one or more tasks (Mode B)."""
        if not tasks:
            return
        self.active_tasks = list(tasks)
        self.active_chip_index = 0
        for t in tasks:
            if t.status == "todo":
                self.db.set_task_status(t.id, "doing")
        self.engine.reset()
        self.engine.start(time.monotonic())
        self._log_new_session()
        # If we're on Kanban, jump to Dashboard so the timer is visible.
        if self.screen.__class__.__name__ != "DashboardScreen":
            try:
                self.switch_screen("dashboard")
            except Exception:
                pass
        self._refresh_all()

    def add_task_from_input(self, text: str) -> Task:
        """Parse inline metadata syntax and create the task.

        Examples:
          "Write report #docs #urgent"           → tags=docs,urgent
          "Write report @client-acme #docs ~3"   → project=client-acme, tags=docs, estimate=3
          "Wire OAuth @work !v1.0 ~5 #backend"   → project=work, sprint=v1.0, tags=backend, est=5
        First @token wins (later ones become title words). First !token wins. First ~N wins.
        """
        words = text.split()
        title_words: list[str] = []
        tags: list[str] = []
        project_name: str | None = None
        sprint_name: str | None = None
        estimate = 0
        for w in words:
            if w.startswith("#") and len(w) > 1:
                tags.append(w[1:])
            elif w.startswith("@") and len(w) > 1 and project_name is None:
                project_name = w[1:]
            elif w.startswith("!") and len(w) > 1 and sprint_name is None:
                sprint_name = w[1:]
            elif w.startswith("~") and len(w) > 1 and estimate == 0:
                try:
                    estimate = int(w[1:])
                except ValueError:
                    title_words.append(w)
            else:
                title_words.append(w)
        title = " ".join(title_words) or text
        project_id: int | None = None
        sprint_id: int | None = None
        if project_name:
            proj = self.db.get_or_create_project(project_name)
            project_id = proj.id
        elif self.project_filter.scoped_project_id is not None:
            # If a real project filter is active, default new tasks to that project.
            project_id = self.project_filter.scoped_project_id
        if sprint_name:
            sp = self.db.get_or_create_sprint(project_id, sprint_name)
            sprint_id = sp.id
        elif self.active_sprint_id is not None and not project_name:
            # Default to the active sprint filter so a new task isn't immediately
            # filtered out of the board it was added from. Only when the user didn't
            # type an explicit @project (the active sprint is scoped to the filter
            # project, so applying it to a different project would be inconsistent).
            sprint_id = self.active_sprint_id
        return self.db.add_task(title, tags=",".join(tags),
                                estimated_pomodoros=estimate,
                                project_id=project_id, sprint_id=sprint_id)

    def delete_task_by_id(self, task_id: int) -> None:
        self.active_tasks = [t for t in self.active_tasks if t.id != task_id]
        self.db.delete_task(task_id)

    # ---------- global actions ----------
    def action_switch(self, name: str) -> None:
        if name in ("dashboard", "kanban", "stats", "history", "projects", "sprints"):
            self.switch_screen(name)
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
            actual = int(time.monotonic() - self.session_start_monotonic)
            self.sessions.end(self.current_session_id, actual_seconds=actual, completed=False)
            self.current_session_id = None
            self.session_start_monotonic = None
        self.engine.reset()
        self._refresh_all()

    def action_skip(self) -> None:
        events = self.engine.skip(time.monotonic())
        if Event.PHASE_COMPLETED in events and self.current_session_id is not None:
            actual = int(time.monotonic() - (self.session_start_monotonic or time.monotonic()))
            self.sessions.end(self.current_session_id, actual_seconds=actual, completed=False)
            self.current_session_id = None
            self.session_start_monotonic = None
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
        from pomodoro.screens.edit_task import EditTaskModal
        project_name = None
        if task.project_id is not None:
            try:
                project_name = self.db.get_project(task.project_id).name
            except Exception:
                project_name = None
        self.push_screen(
            EditTaskModal(task, project_name=project_name),
            lambda result: self._on_task_edited(task.id, result),
        )

    def _on_task_edited(self, task_id: int, result: dict | None) -> None:
        if result is None:
            return
        project_name = (result.get("project") or "").strip()
        if project_name:
            project_id = self.db.get_or_create_project(project_name).id
        else:
            project_id = None
        self.db.update_task(
            task_id,
            title=result["title"],
            tags=result["tags"],
            estimated_pomodoros=result["estimate"],
            project_id=project_id,
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
                task_title = None
        self.push_screen(
            ResumePrompt(task_title, remaining),
            lambda resume: self._on_resume_choice(resume, sid, remaining, phase_str, task_id_str),
        )

    def _on_resume_choice(self, resume: bool | None, sid: int, remaining: int,
                          phase_str: str, task_id_str: str | None) -> None:
        for k in ("pending_session_id", "pending_remaining_seconds", "pending_phase",
                  "pending_task_id"):
            self.db.kv_delete(k)
        if not resume:
            try:
                self.sessions.end(sid, actual_seconds=0, completed=False)
            except Exception:
                pass
            return
        # Resume: load task, restore engine state, log nothing new (reuse session row).
        if task_id_str:
            try:
                self.active_task = self.db.get_task(int(task_id_str))
            except Exception:
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
        # Tear down only the daemon we started (leaves a pre-existing player alone).
        try:
            self.music.stop_daemon()
        except Exception:
            log.exception("stopping music daemon failed")
        if self.config.sync.enabled:
            try:
                git_sync(self.db.path.parent)
            except Exception:
                log.exception("git_sync on shutdown failed")

    def action_pick_preset(self) -> None:
        if not self.config.presets:
            try:
                self.notify("No presets configured. Add [[preset]] entries to your config.toml.", timeout=4)
            except Exception:
                pass
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
        try:
            self.notify(f"Preset '{preset.name}' will apply on next session.", timeout=3)
        except Exception:
            pass

    # ---------- project / sprint filter ----------
    def _load_filter(self, key: str) -> int | None:
        if not hasattr(self, "db") or self.db is None:
            return None
        val = self.db.kv_get(key)
        if not val:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    def _save_filter(self, key: str, value: int | str | None) -> None:
        if value is None:
            self.db.kv_delete(key)
        else:
            self.db.kv_set(key, str(value))

    def set_project_filter(self, pf: ProjectFilter) -> None:
        self.project_filter = pf
        # Switching to All/Inbox, or to a different project, may invalidate the
        # active sprint (sprints are scoped to a project).
        scope_pid = pf.scoped_project_id
        if scope_pid is None:
            if self.active_sprint_id is not None:
                self.active_sprint_id = None
                self._save_filter("ui.active_sprint", None)
        elif self.active_sprint_id is not None:
            try:
                sp = self.db.get_sprint(self.active_sprint_id)
                if sp.project_id != scope_pid:
                    self.active_sprint_id = None
                    self._save_filter("ui.active_sprint", None)
            except Exception:
                self.active_sprint_id = None
                self._save_filter("ui.active_sprint", None)
        self._save_filter("ui.active_project", pf.to_kv())
        self._refresh_all()

    def set_active_project(self, project_id: int | None) -> None:
        """Convenience: filter to a specific project, or All when None."""
        self.set_project_filter(
            ProjectFilter.all() if project_id is None else ProjectFilter.project(project_id)
        )

    def set_active_sprint(self, sprint_id: int | None) -> None:
        self.active_sprint_id = sprint_id
        self._save_filter("ui.active_sprint", sprint_id)
        self._refresh_all()

    def action_pick_project(self) -> None:
        from pomodoro.screens.project_picker import ProjectPickerModal
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
                label = "project"
        try:
            self.notify(f"Project filter: {label}", timeout=2)
        except Exception:
            pass

    def action_cycle_project(self) -> None:
        """Cycle through: All → each project → Inbox → All ..."""
        projects = self.db.list_projects()
        cycle = ([ProjectFilter.all()]
                 + [ProjectFilter.project(p.id) for p in projects]
                 + [ProjectFilter.inbox()])
        try:
            idx = cycle.index(self.project_filter)
        except ValueError:
            idx = 0
        nxt = cycle[(idx + 1) % len(cycle)]
        self.set_project_filter(nxt)
        label = self.active_project_label() or "All"
        try:
            self.notify(f"Project: {label}", timeout=2)
        except Exception:
            pass

    def project_filter_for_db(self):
        """Translate the active filter into the db.list_tasks `project_filter` value."""
        return self.project_filter.for_db()

    def active_project_label(self) -> str | None:
        pf = self.project_filter
        if pf.is_all:
            return None
        if pf.is_inbox:
            return "Inbox"
        try:
            return self.db.get_project(pf.project_id).name
        except Exception:
            return None

    def active_project_color(self) -> str:
        if not self.project_filter.is_project:
            return "white"
        try:
            return self.db.get_project(self.project_filter.project_id).color
        except Exception:
            return "white"

    def action_pick_sprint(self) -> None:
        from pomodoro.screens.sprint_picker import SprintPickerModal
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
        from pomodoro.core.timer_engine import Phase
        breaks = getattr(self.config, "breaks", None)
        minutes = breaks.lunch_minutes if breaks else 45
        self._start_long_pause(minutes * 60, label="lunch")

    def _start_long_pause(self, seconds: int, label: str = "long_pause") -> None:
        from pomodoro.core.timer_engine import Phase
        # If a session is running, log an interruption with reason, end it as incomplete.
        if self.current_session_id is not None and self.session_start_monotonic is not None:
            actual = int(time.monotonic() - self.session_start_monotonic)
            try:
                self.sessions.log_interruption(self.current_session_id, reason=label)
            except Exception:
                pass
            self.sessions.end(self.current_session_id, actual_seconds=actual, completed=False)
            self.current_session_id = None
            self.session_start_monotonic = None
        # Remember the phase we interrupted so the engine resumes it after the pause.
        prev_phase = self.engine.phase
        self.engine.enter_long_pause(seconds, time.monotonic(), resume_phase=prev_phase)
        # Log the long pause as a session.
        self.current_session_id = self.sessions.start("long_pause", seconds, task_ids=[])
        self.session_start_monotonic = time.monotonic()
        try:
            self.notify(f"⏸  {label} started ({seconds // 60} min)", timeout=3)
        except Exception:
            pass
        self._refresh_all()

    def action_music_toggle(self) -> None:
        self.music.toggle()
        if self.config.music.enabled:
            try:
                self.notify("♪ play / pause", timeout=2)
            except Exception:
                pass

    def action_music_next(self) -> None:
        self.music.next()
        if self.config.music.enabled:
            try:
                self.notify("♪ ⏭ next track", timeout=2)
            except Exception:
                pass

    def action_toggle_auto_advance(self) -> None:
        self.config.timer.auto_advance = not self.config.timer.auto_advance
        state = "on" if self.config.timer.auto_advance else "off"
        try:
            self.notify(f"Auto-advance {state}", timeout=2)
        except Exception:
            pass
        if self.config_path is not None:
            try:
                save_config(self.config, self.config_path)
            except Exception:
                pass

    def action_cycle_theme(self) -> None:
        self._theme_idx = (self._theme_idx + 1) % len(THEMES)
        name = THEMES[self._theme_idx]
        try:
            self.theme = name
        except Exception:
            pass
        self.config.ui.theme = name
        if self.config_path is not None:
            try:
                save_config(self.config, self.config_path)
            except Exception:
                pass
