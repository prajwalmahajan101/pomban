"""Live session bookkeeping + the engine⇄DB⇄SessionService wiring.

UI-free: the app owns modals, notifications, phase hooks and music; this object
just opens/closes the DB session rows, tracks the current session id and its
wall-clock start, and answers the lunch-suggestion question. Extracted from the
app shell so the session lifecycle is testable without Textual.
"""

from __future__ import annotations

import time
from datetime import datetime

from pomodoro.core.timer_engine import Phase


class SessionCoordinator:
    def __init__(self, engine, db, sessions) -> None:
        self.engine = engine
        self.db = db
        self.sessions = sessions
        self.current_session_id: int | None = None
        self.session_start_monotonic: float | None = None

    def elapsed(self) -> int:
        """Wall-clock seconds since the current session started (0 if none)."""
        if self.session_start_monotonic is None:
            return 0
        return int(time.monotonic() - self.session_start_monotonic)

    def begin(self, task_ids: list[int]) -> None:
        """Open a DB session row for the engine's current (non-idle) phase."""
        if self.engine.phase == Phase.IDLE:
            return
        planned = {
            Phase.FOCUS: self.engine.settings.focus_seconds,
            Phase.SHORT_BREAK: self.engine.settings.short_break_seconds,
            Phase.LONG_BREAK: self.engine.settings.long_break_seconds,
            Phase.LONG_PAUSE: self.engine.remaining or 45 * 60,
        }.get(self.engine.phase, 0)
        self.current_session_id = self.sessions.start(self.engine.phase.value, planned, task_ids)
        self.session_start_monotonic = time.monotonic()

    def end(self, actual: int, *, completed: bool) -> None:
        """End the current session row (if any) and clear the bookkeeping."""
        if self.current_session_id is not None:
            self.sessions.end(self.current_session_id, actual_seconds=actual, completed=completed)
        self.current_session_id = None
        self.session_start_monotonic = None

    def should_suggest_lunch(self, completed_phase: Phase, config) -> bool:
        """True iff a focus just completed, now is inside the configured lunch
        window, and lunch hasn't been taken today (cached — safe on the tick)."""
        if completed_phase != Phase.FOCUS:
            return False
        breaks = getattr(config, "breaks", None)
        if breaks is None or not breaks.lunch_window_start or not breaks.lunch_window_end:
            return False
        try:
            now = datetime.now().time()
            start_h, start_m = (int(x) for x in breaks.lunch_window_start.split(":"))
            end_h, end_m = (int(x) for x in breaks.lunch_window_end.split(":"))
        except Exception:
            return False
        start, end, cur = (start_h, start_m), (end_h, end_m), (now.hour, now.minute)
        if not (start <= cur <= end):
            return False
        return not self.sessions.lunch_taken_today()
