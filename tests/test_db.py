import tempfile
from pathlib import Path

import pytest

from pomodoro.core.db import DB


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as td:
        d = DB(Path(td) / "test.db")
        yield d
        d.close()


def test_add_and_list_task(db):
    t = db.add_task("Write report")
    assert t.id > 0
    assert t.status == "todo"
    tasks = db.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].title == "Write report"


def test_status_change_and_delete(db):
    t = db.add_task("X")
    db.set_task_status(t.id, "doing")
    assert db.get_task(t.id).status == "doing"
    db.delete_task(t.id)
    assert db.list_tasks() == []


def test_session_lifecycle_and_stats(db):
    t = db.add_task("Y")
    sid = db.start_session("focus", 1500, [t.id])
    db.end_session(sid, actual_seconds=1500, completed=True)
    s = db.stats_today()
    assert s["sessions"] == 1
    assert s["focus_seconds"] == 1500
    assert s["streak"] == 1


def test_delete_task_with_sessions_cascades(db):
    # ISSUE-010: session_tasks.task_id now has ON DELETE CASCADE, so deleting a
    # task that was part of a focus session must not raise and must not orphan rows.
    t = db.add_task("Tracked task")
    sid = db.start_session("focus", 1500, [t.id])
    db.end_session(sid, actual_seconds=1500, completed=True)
    assert (
        db.conn.execute("SELECT COUNT(*) FROM session_tasks WHERE task_id=?", (t.id,)).fetchone()[0]
        == 1
    )
    db.delete_task(t.id)  # must not raise
    assert (
        db.conn.execute("SELECT COUNT(*) FROM session_tasks WHERE task_id=?", (t.id,)).fetchone()[0]
        == 0
    )


def test_schema_is_current(db):
    from pomodoro.core.db import SCHEMA_VERSION

    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_project_color_is_deterministic(db):
    # ISSUE-006: same name → same palette color, regardless of process hash seed.
    p1 = db.get_or_create_project("Acme")
    db.delete_project(p1.id)
    p2 = db.get_or_create_project("Acme")
    assert p1.color == p2.color


def test_migration_v8_drops_stale_kind_check(tmp_path):
    # Reproduce a pre-existing DB: sessions.kind has the old CHECK that forbids
    # 'long_pause', plus the FK children, stamped at user_version 7.
    import sqlite3

    p = tmp_path / "old.db"
    raw = sqlite3.connect(str(p))
    raw.executescript(
        """
        CREATE TABLE sessions (
          id INTEGER PRIMARY KEY,
          kind TEXT NOT NULL CHECK(kind IN ('focus','short_break','long_break')),
          started_at TEXT NOT NULL, ended_at TEXT,
          planned_seconds INTEGER NOT NULL,
          actual_seconds INTEGER NOT NULL DEFAULT 0,
          completed INTEGER NOT NULL DEFAULT 0,
          interruption_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE session_tasks (
          session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
          task_id INTEGER, completed_during_session INTEGER DEFAULT 0,
          PRIMARY KEY (session_id, task_id)
        );
        INSERT INTO sessions (kind, started_at, planned_seconds) VALUES ('focus','2026-01-01T09:00:00',1500);
        INSERT INTO session_tasks (session_id, task_id) VALUES (1, 1);
        CREATE TABLE tasks (
          id INTEGER PRIMARY KEY, title TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('todo','doing','done')),
          tags TEXT DEFAULT '', estimated_pomodoros INTEGER DEFAULT 0,
          position INTEGER DEFAULT 0, project_id INTEGER, sprint_id INTEGER,
          notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        PRAGMA user_version = 7;
        """
    )
    raw.commit()
    raw.close()

    db = DB(p)  # runs migration v8
    try:
        from pomodoro.core.db import SCHEMA_VERSION

        assert db.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        # Existing data survived the rebuild (no cascade wipe).
        assert db.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
        assert db.conn.execute("SELECT COUNT(*) FROM session_tasks").fetchone()[0] == 1
        # The previously-forbidden kind now inserts cleanly.
        sid = db.start_session("long_pause", 2700, [])
        assert (
            db.conn.execute("SELECT kind FROM sessions WHERE id=?", (sid,)).fetchone()[0]
            == "long_pause"
        )
    finally:
        db.close()
