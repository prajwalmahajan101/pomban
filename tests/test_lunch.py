"""Tests for Phase I5: LONG_PAUSE phase and lunch break action."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pomban.app import PomodoroApp
from pomban.core.config import BreaksSection, Config
from pomban.core.db import DB
from pomban.core.timer_engine import Phase


def _make_app(tmp_db: Path, breaks: BreaksSection | None = None) -> PomodoroApp:
    cfg = Config()
    if breaks:
        cfg.breaks = breaks
    db = DB(tmp_db)
    return PomodoroApp(db=db, config=cfg, fast=True)


def test_long_pause_phase_exists():
    assert Phase.LONG_PAUSE.value == "long_pause"


def test_start_long_pause_enters_long_pause_state():
    p = Path(tempfile.mktemp(suffix=".db"))
    app = _make_app(p, BreaksSection(lunch_minutes=30))
    app._start_long_pause(30 * 60, label="lunch")
    assert app.engine.phase == Phase.LONG_PAUSE
    assert app.engine.remaining == 30 * 60
    assert app.engine.running
    # Session row recorded with kind=long_pause
    row = app.db.conn.execute(
        "SELECT kind, planned_seconds FROM sessions WHERE id = ?",
        (app.current_session_id,),
    ).fetchone()
    assert row["kind"] == "long_pause"
    assert row["planned_seconds"] == 30 * 60
    app.db.close()
    p.unlink(missing_ok=True)


def test_should_suggest_lunch_disabled_without_window():
    p = Path(tempfile.mktemp(suffix=".db"))
    app = _make_app(p, BreaksSection())  # empty window strings
    assert app._should_suggest_lunch(Phase.FOCUS) is False
    app.db.close()
    p.unlink(missing_ok=True)


def test_should_not_suggest_after_break_phase():
    p = Path(tempfile.mktemp(suffix=".db"))
    app = _make_app(p, BreaksSection(lunch_window_start="12:00", lunch_window_end="13:00"))
    assert app._should_suggest_lunch(Phase.SHORT_BREAK) is False
    assert app._should_suggest_lunch(Phase.LONG_BREAK) is False
    app.db.close()
    p.unlink(missing_ok=True)
