"""PombanEngine — UI-agnostic facade over the timer, session, and plugin layers.

Composes the three already-UI-free cores (``TimerEngine``, ``SessionService``,
``SessionCoordinator``) and adds the orchestration that used to live in
``app.py``: active-task tracking, plugin-hook firing, and a tick loop that
returns plain dataclasses describing what the app should do next
(``TickOutcome``). The engine never imports Textual.

The Textual ``App`` retains responsibility for side effects that touch the
screen — bell, toast, modal push, screen refresh — but reads its work plan
from this object. Screens can hold a reference to ``PombanEngine`` and remain
agnostic to the Textual app shell.

This module is being introduced incrementally. C1 lands the scaffold + API
shape; C2–C4 progressively migrate the tick loop, session lifecycle, and
active-task state out of ``app.py`` and into here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, timedelta

from pomban.core import log
from pomban.core.models import Sprint, Task
from pomban.core.session_coordinator import SessionCoordinator
from pomban.core.session_service import SessionService
from pomban.core.timer_engine import Event, Phase, Settings, TimerEngine


@dataclass(frozen=True)
class TickOutcome:
    """One action the app shell should take after a tick.

    The engine never imports Textual; it emits these as a plan and lets the
    app decide how to realise them (bell, toast, modal, screen refresh).
    """

    kind: str  # "ending_soon" | "phase_completed" | "auto_advanced"
    phase: Phase | None = None
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SessionResult:
    """Outcome of finalising a session row (used by C3)."""

    completed: bool
    actual_seconds: int
    completed_tasks: list[int] = field(default_factory=list)


class PombanEngine:
    """Composition root for the timer + session + plugin layers.

    Holds the active-task set, owns the ``TimerEngine`` / ``SessionService`` /
    ``SessionCoordinator`` trio, and exposes a small UI-agnostic API the
    Textual app shell drives.
    """

    def __init__(
        self,
        db,
        sessions: SessionService | None = None,
        coord: SessionCoordinator | None = None,
        settings: Settings | None = None,
        timer: TimerEngine | None = None,
        plugin_registry=None,
        hooks=None,
        run_hook=None,
        filters=None,
    ) -> None:
        self.db = db
        self.sessions = sessions or SessionService(db)
        self.timer = timer or TimerEngine(settings=settings or Settings())
        self.coord = coord or SessionCoordinator(self.timer, self.db, self.sessions)
        self._plugin_registry = plugin_registry
        self._hooks = hooks
        self._run_hook = run_hook
        # FilterState reference so engine.active_sprint / sprint-target checks
        # can read the user's active sprint without going through the app shell.
        # Optional so unit tests can drive the engine without a filter store.
        self._filters = filters
        self.active_tasks: list[Task] = []
        self.active_chip_index: int = 0

    # ---------- timer delegation (screens & app shell read these) ----------
    @property
    def phase(self) -> Phase:
        return self.timer.phase

    @property
    def remaining(self) -> int:
        return self.timer.remaining

    @property
    def running(self) -> bool:
        return self.timer.running

    @property
    def completed_focus_cycles(self) -> int:
        return self.timer.completed_focus_cycles

    @property
    def settings(self) -> Settings:
        return self.timer.settings

    @settings.setter
    def settings(self, value: Settings) -> None:
        self.timer.settings = value

    # ---------- session bookkeeping passthrough ----------
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

    # ---------- active-task helpers (C4 migrates app.py to use these) ----------
    @property
    def active_task(self) -> Task | None:
        return self.active_tasks[0] if self.active_tasks else None

    @active_task.setter
    def active_task(self, task: Task | None) -> None:
        self.active_tasks = [task] if task else []

    # ---------- tick loop (C2 migrates app.py to use this) ----------
    def tick(self, now: float) -> list[TickOutcome]:
        """Advance the timer and return a plan of UI-side effects.

        The app shell loops over the returned outcomes and realises each:
        ``ending_soon`` → bell + toast; ``phase_completed`` → push the
        session-end modal (unless ``auto_advance`` already handled it).
        """
        if not self.timer.running:
            return []
        events = self.timer.tick(now)
        return self._events_to_outcomes(events)

    def _events_to_outcomes(self, events: list[Event]) -> list[TickOutcome]:
        out: list[TickOutcome] = []
        if Event.PHASE_ENDING_SOON in events:
            out.append(TickOutcome(kind="ending_soon", phase=self.timer.phase))
        if Event.PHASE_COMPLETED in events:
            out.append(TickOutcome(kind="phase_completed", phase=self.timer.phase))
        return out

    # ---------- plugin / hook firing (C3 migrates app.py to use this) ----------
    def fire_phase_hooks(self, *, starting: bool, phase: Phase) -> None:
        """Run the user's shell hook for this phase + dispatch in-process plugins.

        Mirrors the old ``app._fire_phase_hooks`` exactly so the migration is
        a relocation, not a behaviour change. Skipped silently if the engine
        was constructed without a hook config (unit-test usage).
        """
        task_title = self.active_task.title if self.active_task else ""
        env = {
            "POMODORO_PHASE": phase.value,
            "POMODORO_TASK_TITLE": task_title,
            "POMODORO_EVENT": "start" if starting else "end",
        }
        if self._hooks is not None and self._run_hook is not None:
            if phase == Phase.FOCUS:
                cmd = self._hooks.on_focus_start if starting else self._hooks.on_focus_end
            else:
                cmd = self._hooks.on_break_start if starting else self._hooks.on_break_end
            try:
                self._run_hook(cmd, env)
            except Exception:
                log.exception("phase hook failed (phase=%s starting=%s)", phase.value, starting)
        if self._plugin_registry is not None:
            try:
                reg = self._plugin_registry()
                if starting:
                    reg.fire("on_phase_started", phase.value, task_title or None)
                else:
                    reg.fire("on_phase_completed", phase.value, task_title or None, True)
            except Exception:
                log.exception(
                    "plugin dispatch failed (phase=%s starting=%s)", phase.value, starting
                )

    # ---------- session lifecycle ----------
    def log_new_session(self) -> None:
        """Open a DB session row for the timer's current phase and fire start hooks.

        Idle phase = nothing to log. For non-FOCUS phases (breaks, long pause)
        we still record the session but with no associated tasks.
        """
        if self.timer.phase == Phase.IDLE:
            return
        self.fire_phase_hooks(starting=True, phase=self.timer.phase)
        task_ids = [t.id for t in self.active_tasks] if self.timer.phase == Phase.FOCUS else []
        self.coord.begin(task_ids)

    def start_focus_on_many(self, tasks: list[Task]) -> bool:
        """Begin a focus session over one or more tasks.

        Marks any todo tasks as doing, resets+starts the timer, and opens the
        session row. Returns True if the app shell should switch to the
        Dashboard so the timer is visible (false when no tasks were supplied).
        """
        if not tasks:
            return False
        self.active_tasks = list(tasks)
        self.active_chip_index = 0
        for t in tasks:
            if t.status == "todo":
                self.db.set_task_status(t.id, "doing")
        self.timer.reset()
        self.timer.start(time.monotonic())
        self.log_new_session()
        return True

    # ---------- sprint surface (M3) ----------
    @property
    def active_sprint(self) -> Sprint | None:
        """Sprint the user is currently focused on (per FilterState), or None."""
        if self._filters is None or self._filters.sprint_id is None:
            return None
        try:
            return self.db.get_sprint(self._filters.sprint_id)
        except Exception:
            log.exception("active_sprint: get_sprint failed")
            return None

    def active_sprint_progress(self) -> dict | None:
        """Combined ``sprint_progress`` payload + the sprint row, or None.

        Returned dict keys: ``target``, ``completed``, ``pct``, ``days_left``,
        ``pace``, ``on_track``, ``sprint``. UI reads this to render headers
        and the runner overlay without two round trips.
        """
        sp = self.active_sprint
        if sp is None:
            return None
        try:
            payload = dict(self.db.sprint_progress(sp.id))
        except Exception:
            log.exception("active_sprint_progress: sprint_progress failed")
            return None
        payload["sprint"] = sp
        return payload

    def sprint_tasks(self, sprint_id: int) -> list[Task]:
        """All tasks (any status) belonging to the given sprint."""
        try:
            return self.db.list_tasks(sprint_id=sprint_id, include_done=True)
        except Exception:
            log.exception("sprint_tasks: list_tasks failed")
            return []

    def create_sprint_for_project(
        self, project_id: int, name: str | None = None, days: int = 14
    ) -> Sprint:
        """Create + activate a sprint scoped to the project.

        Auto-names ``"Sprint N"`` based on the project's existing sprint count
        when ``name`` is None. Default duration 14 days; ``pomodoro_target``
        starts at 0 and can be edited later. Activation deactivates any sibling.
        """
        if name is None:
            existing = self.db.list_sprints(project_id=project_id)
            name = f"Sprint {len(existing) + 1}"
        today = date.today()
        end = today + timedelta(days=days)
        sp = self.db.add_sprint(
            project_id,
            name,
            today.isoformat(),
            end.isoformat(),
            goal="",
            status="planned",
        )
        self.db.activate_sprint(sp.id)
        return self.db.get_sprint(sp.id)

    def close_sprint(self, sprint_id: int, retrospective: str) -> None:
        """Mark sprint completed with a retrospective note."""
        self.db.update_sprint(sprint_id, status="completed", retrospective=retrospective)

    def update_sprint_retro(self, sprint_id: int, retrospective: str) -> None:
        """Update the retrospective without changing status (used by ``e`` edit)."""
        self.db.update_sprint(sprint_id, retrospective=retrospective)

    # ---------- first-run detection (M3) ----------
    def is_first_run(self) -> bool:
        """True when the library has no user-created projects yet.

        The app shell uses this on mount to decide whether to push the
        FirstRunModal before the dashboard becomes interactive.
        """
        try:
            return not self.db.list_projects()
        except Exception:
            log.exception("is_first_run: list_projects failed")
            return False

    def finalize_multi_complete(self, sid: int | None, actual: int, ids: list[int] | None) -> None:
        """Close a multi-task focus session and mark the indicated tasks done."""
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
        self.timer.confirm_advance(time.monotonic())
        self.log_new_session()


__all__ = [
    "PombanEngine",
    "SessionResult",
    "TickOutcome",
]
