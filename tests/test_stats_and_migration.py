import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pomodoro.core.db import DB
from pomodoro.widgets.heatmap import BLOCKS, render_heatmap


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as td:
        d = DB(Path(td) / "s.db")
        yield d
        d.close()


# ---------- DB ----------

def test_log_interruption_increments_counter(db):
    t = db.add_task("X")
    sid = db.start_session("focus", 1500, [t.id])
    db.log_interruption(sid, "phone call")
    db.log_interruption(sid)
    row = db.conn.execute("SELECT interruption_count FROM sessions WHERE id=?", (sid,)).fetchone()
    assert row["interruption_count"] == 2
    rows = db.conn.execute("SELECT * FROM interruptions WHERE session_id=?", (sid,)).fetchall()
    assert len(rows) == 2
    assert rows[0]["reason"] == "phone call"


def test_daily_focus_minutes_fills_zero_days(db):
    data = db.daily_focus_minutes(7)
    assert len(data) == 7
    assert all(m == 0 for _, m in data)


def test_daily_focus_minutes_counts_completed_only(db):
    t = db.add_task("X")
    sid = db.start_session("focus", 1500, [t.id])
    db.end_session(sid, actual_seconds=600, completed=True)
    sid2 = db.start_session("focus", 1500, [t.id])
    db.end_session(sid2, actual_seconds=300, completed=False)  # not counted
    data = db.daily_focus_minutes(7)
    assert data[-1][1] == 10  # only the completed one


def test_top_tasks(db):
    a = db.add_task("Aaa")
    b = db.add_task("Bbb")
    sid1 = db.start_session("focus", 1500, [a.id])
    db.end_session(sid1, actual_seconds=1500, completed=True)
    sid2 = db.start_session("focus", 1500, [b.id])
    db.end_session(sid2, actual_seconds=600, completed=True)
    top = db.top_tasks()
    assert top[0][0] == "Aaa"
    assert top[1][0] == "Bbb"


def test_session_history_orders_descending(db):
    t = db.add_task("T")
    for _ in range(3):
        sid = db.start_session("focus", 100, [t.id])
        db.end_session(sid, actual_seconds=100, completed=True)
    hist = db.session_history()
    assert len(hist) == 3
    assert hist[0]["started_at"] >= hist[-1]["started_at"]


def test_migration_v1_to_v2_upgrades_existing_db(tmp_path):
    """Build a v1-only schema by hand, point DB at it, expect v2 after open."""
    db_path = tmp_path / "old.db"
    raw = sqlite3.connect(str(db_path))
    raw.executescript(
        """
        CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL,
                            tags TEXT DEFAULT '', estimated_pomodoros INTEGER DEFAULT 0,
                            position INTEGER DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE sessions (id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
                               started_at TEXT NOT NULL, ended_at TEXT,
                               planned_seconds INTEGER NOT NULL, actual_seconds INTEGER NOT NULL DEFAULT 0,
                               completed INTEGER NOT NULL DEFAULT 0,
                               interruption_count INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE session_tasks (session_id INTEGER, task_id INTEGER,
                                    completed_during_session INTEGER DEFAULT 0,
                                    PRIMARY KEY (session_id, task_id));
        CREATE TABLE config_kv (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO tasks (title, status, created_at, updated_at)
            VALUES ('Existing', 'todo', '2024-01-01', '2024-01-01');
        PRAGMA user_version = 1;
        """
    )
    raw.commit()
    raw.close()

    db = DB(db_path)
    # interruptions table now exists
    db.conn.execute("SELECT COUNT(*) FROM interruptions").fetchone()
    # user_version bumped
    v = db.conn.execute("PRAGMA user_version").fetchone()[0]
    assert v == 2
    # Old row preserved
    rows = db.conn.execute("SELECT title FROM tasks").fetchall()
    assert rows[0]["title"] == "Existing"
    db.close()


# ---------- Heatmap renderer ----------

def test_heatmap_renders_correct_block_density():
    data = [("2026-05-20", 0), ("2026-05-21", 60), ("2026-05-22", 200)]
    out = render_heatmap(data, cell_per_step=30)
    # first day zero → "·", second 60 (idx=2) → "▒", third 200 (idx=4) → "█"
    assert BLOCKS[0] in out
    assert BLOCKS[2] in out
    assert BLOCKS[4] in out


def test_heatmap_handles_empty():
    assert "no data" in render_heatmap([])
