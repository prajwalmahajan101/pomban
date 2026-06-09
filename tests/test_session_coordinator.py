import tempfile
import time
from pathlib import Path

from pomodoro.core.config import BreaksSection, Config
from pomodoro.core.db import DB
from pomodoro.core.session_coordinator import SessionCoordinator
from pomodoro.core.session_service import SessionService
from pomodoro.core.timer_engine import Phase, Settings, TimerEngine


def _coord(td):
    db = DB(Path(td) / "s.db")
    eng = TimerEngine(settings=Settings(focus_seconds=1500))
    return SessionCoordinator(eng, db, SessionService(db)), db, eng


def test_begin_is_noop_when_idle():
    with tempfile.TemporaryDirectory() as td:
        coord, db, _eng = _coord(td)
        coord.begin([])  # engine is IDLE
        assert coord.current_session_id is None
        db.close()


def test_begin_then_end_focus_persists_row():
    with tempfile.TemporaryDirectory() as td:
        coord, db, eng = _coord(td)
        eng.restore(Phase.FOCUS, 1500, running=True, now=time.monotonic())
        coord.begin([])
        sid = coord.current_session_id
        assert sid is not None and coord.session_start_monotonic is not None
        coord.end(1500, completed=True)
        assert coord.current_session_id is None and coord.session_start_monotonic is None
        row = db.conn.execute(
            "SELECT kind, completed, actual_seconds FROM sessions WHERE id=?", (sid,)
        ).fetchone()
        assert row["kind"] == "focus" and row["completed"] == 1 and row["actual_seconds"] == 1500
        db.close()


def test_end_without_session_is_safe():
    with tempfile.TemporaryDirectory() as td:
        coord, db, _eng = _coord(td)
        coord.end(10, completed=False)  # must not raise
        assert coord.current_session_id is None
        assert coord.elapsed() == 0
        db.close()


def test_should_suggest_lunch_respects_phase_and_window():
    with tempfile.TemporaryDirectory() as td:
        coord, db, _eng = _coord(td)
        cfg = Config()
        cfg.breaks = BreaksSection(
            lunch_minutes=45, lunch_window_start="00:00", lunch_window_end="23:59"
        )
        assert coord.should_suggest_lunch(Phase.FOCUS, cfg) is True
        assert coord.should_suggest_lunch(Phase.SHORT_BREAK, cfg) is False
        assert coord.should_suggest_lunch(Phase.FOCUS, Config()) is False  # no window set
        db.close()
