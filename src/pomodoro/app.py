from __future__ import annotations

import time

from textual.app import App
from textual.binding import Binding

from pomodoro.core import config as cfg_module
from pomodoro.core.config import Config, save as save_config
from pomodoro.core.db import DB
from pomodoro.core.models import Task
from pomodoro.core.timer_engine import Event, Phase, Settings, TimerEngine
from pomodoro.notifications import NotifyConfig, fire, run_hook
from pomodoro.plugins import git_sync, registry as plugin_registry
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
    ]

    def __init__(self, db: DB | None = None, fast: bool = False, settings: Settings | None = None,
                 notify_cfg: NotifyConfig | None = None, config: Config | None = None,
                 config_path=None) -> None:
        super().__init__()
        self.config = config or cfg_module.load(config_path)
        self.config_path = config_path
        self.db = db or DB()
        if settings is None:
            settings = (Settings(focus_seconds=5, short_break_seconds=3, long_break_seconds=4,
                                 cycles_before_long_break=4, warning_seconds=2)
                        if fast else cfg_module.to_settings(self.config))
        if notify_cfg is None:
            notify_cfg = cfg_module.to_notify_config(self.config)
        self.engine = TimerEngine(settings=settings)
        self.notify_cfg = notify_cfg
        self.active_task: Task | None = None
        self.current_session_id: int | None = None
        self.session_start_monotonic: float | None = None
        try:
            self._theme_idx = THEMES.index(self.config.ui.theme)
        except ValueError:
            self._theme_idx = 0
        self._pending_actual_seconds = 0

    def on_mount(self) -> None:
        self.install_screen(DashboardScreen(), name="dashboard")
        self.install_screen(KanbanScreen(), name="kanban")
        self.install_screen(StatsScreen(), name="stats")
        self.install_screen(HistoryScreen(), name="history")
        self.push_screen("dashboard")
        plugin_registry().discover()
        self._maybe_prompt_resume()
        self.set_interval(0.25, self._tick)
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
        scr = self.screen
        if hasattr(scr, "refresh_timer"):
            try:
                scr.refresh_timer()
            except Exception:
                pass

    def _refresh_all(self) -> None:
        for scr in (self.screen,):
            for fn in ("refresh_tasks", "refresh_timer", "refresh_stats", "refresh_board"):
                f = getattr(scr, fn, None)
                if callable(f):
                    try:
                        f()
                    except Exception:
                        pass

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
        self.push_screen(
            SessionEndScreen(completed_phase=completed_phase, task_title=task_title),
            self._on_session_end_result,
        )
        self._refresh_active_screen_timer()

    def _on_session_end_result(self, result: dict | None) -> None:
        actual = self._pending_actual_seconds
        sid = self.current_session_id
        if result is None:
            return
        action = result.get("action")
        if action == "extend":
            extra = int(result.get("seconds", 0))
            if sid is not None and extra > 0:
                self.db.extend_session_planned(sid, extra)
            self.engine.extend(extra, time.monotonic())
            self._refresh_all()
            return
        completed_flag = action == "complete"
        if sid is not None:
            self.db.end_session(sid, actual_seconds=actual, completed=completed_flag)
        self.current_session_id = None
        self.session_start_monotonic = None
        if action == "complete" and self.active_task is not None:
            self.db.set_task_status(self.active_task.id, "done")
            self.active_task = None
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

    def _log_new_session(self) -> None:
        if self.engine.phase == Phase.IDLE:
            return
        self._fire_phase_hooks(starting=True, phase=self.engine.phase)
        task_ids = (
            [self.active_task.id]
            if (self.active_task and self.engine.phase == Phase.FOCUS)
            else []
        )
        planned = {
            Phase.FOCUS: self.engine.settings.focus_seconds,
            Phase.SHORT_BREAK: self.engine.settings.short_break_seconds,
            Phase.LONG_BREAK: self.engine.settings.long_break_seconds,
        }[self.engine.phase]
        self.current_session_id = self.db.start_session(
            self.engine.phase.value, planned, task_ids
        )
        self.session_start_monotonic = time.monotonic()

    # ---------- public API used by screens ----------
    def start_focus_on(self, task: Task) -> None:
        self.active_task = task
        if task.status == "todo":
            self.db.set_task_status(task.id, "doing")
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
        # Parse inline #tags: "Write report #docs #urgent" → title="Write report", tags="docs,urgent"
        words = text.split()
        title_words, tags = [], []
        for w in words:
            if w.startswith("#") and len(w) > 1:
                tags.append(w[1:])
            else:
                title_words.append(w)
        title = " ".join(title_words) or text
        return self.db.add_task(title, tags=",".join(tags))

    def delete_task_by_id(self, task_id: int) -> None:
        if self.active_task and self.active_task.id == task_id:
            self.active_task = None
        self.db.delete_task(task_id)

    # ---------- global actions ----------
    def action_switch(self, name: str) -> None:
        if name in ("dashboard", "kanban", "stats", "history"):
            self.switch_screen(name)
            scr = self.screen
            for fn in ("refresh_stats_screen", "refresh_board", "refresh_tasks", "refresh_timer"):
                f = getattr(scr, fn, None)
                if callable(f):
                    try:
                        f()
                    except Exception:
                        pass

    def action_toggle(self) -> None:
        was_idle = self.engine.phase == Phase.IDLE
        was_running_focus = self.engine.running and self.engine.phase == Phase.FOCUS
        events = self.engine.toggle(time.monotonic())
        if was_idle and self.engine.phase == Phase.FOCUS:
            self._log_new_session()
        elif was_running_focus and not self.engine.running and self.current_session_id is not None:
            # User paused mid-focus — log as an interruption.
            self.db.log_interruption(self.current_session_id)
        self._handle_events(events)
        self._refresh_all()

    def action_reset(self) -> None:
        if self.current_session_id is not None and self.session_start_monotonic is not None:
            actual = int(time.monotonic() - self.session_start_monotonic)
            self.db.end_session(self.current_session_id, actual_seconds=actual, completed=False)
            self.current_session_id = None
            self.session_start_monotonic = None
        self.engine.reset()
        self._refresh_all()

    def action_skip(self) -> None:
        events = self.engine.skip(time.monotonic())
        if Event.PHASE_COMPLETED in events and self.current_session_id is not None:
            actual = int(time.monotonic() - (self.session_start_monotonic or time.monotonic()))
            self.db.end_session(self.current_session_id, actual_seconds=actual, completed=False)
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
            if self.active_task and self.active_task.id == sel.id:
                self.active_task = None
            self._refresh_all()

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

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
                self.db.end_session(sid, actual_seconds=0, completed=False)
            except Exception:
                pass
            return
        # Resume: load task, restore engine state, log nothing new (reuse session row).
        if task_id_str:
            try:
                self.active_task = self.db.get_task(int(task_id_str))
            except Exception:
                self.active_task = None
        self.engine.reset()
        self.engine.phase = Phase(phase_str)
        self.engine.remaining = remaining
        self.engine.running = True
        self.engine._last_tick = time.monotonic()
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
                pass

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
