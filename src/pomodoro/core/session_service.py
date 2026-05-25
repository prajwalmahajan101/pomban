"""Session persistence + lunch-eligibility, extracted from the app god-object.

Two jobs:

1. A thin, named home for the session-row lifecycle (start / end / extend /
   interruption) so ``app.py`` orchestrates rather than embeds SQL plumbing.
2. Owns the lunch-suggestion check and **caches** its per-day result. The old
   code ran a ``COUNT(*)`` on the sessions table from inside the phase-completion
   path (which fires from the 0.25 s tick callback). Caching collapses that to at
   most one query per day, keeping I/O out of the hot path.
"""
from __future__ import annotations

from datetime import date


class SessionService:
    def __init__(self, db) -> None:
        self.db = db
        self._lunch_cache: tuple[str, bool] | None = None  # (iso_date, taken)

    # ---- lifecycle ----
    def start(self, kind: str, planned_seconds: int, task_ids: list[int] | None = None) -> int:
        if kind == "long_pause":
            self._lunch_cache = None  # a pause just started → invalidate
        return self.db.start_session(kind, planned_seconds, task_ids or [])

    def end(self, session_id: int, actual_seconds: int, completed: bool) -> None:
        self.db.end_session(session_id, actual_seconds=actual_seconds, completed=completed)

    def extend_planned(self, session_id: int, extra_seconds: int) -> None:
        self.db.extend_session_planned(session_id, extra_seconds)

    def log_interruption(self, session_id: int, reason: str = "") -> None:
        self.db.log_interruption(session_id, reason=reason)

    # ---- lunch eligibility (cached) ----
    def lunch_taken_today(self) -> bool:
        today = date.today().isoformat()
        if self._lunch_cache is not None and self._lunch_cache[0] == today:
            return self._lunch_cache[1]
        row = self.db.conn.execute(
            "SELECT COUNT(*) AS n FROM sessions"
            " WHERE kind='long_pause' AND substr(started_at,1,10)=?",
            (today,),
        ).fetchone()
        taken = int(row["n"] or 0) > 0
        self._lunch_cache = (today, taken)
        return taken
