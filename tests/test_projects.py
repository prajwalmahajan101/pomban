"""Tests for Phase I: projects, @project inline parser, filter sentinel, migration v3."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from pomban.core.db import DB, SCHEMA_VERSION


@pytest.fixture
def db():
    p = Path(tempfile.mktemp(suffix=".db"))
    d = DB(p)
    yield d
    d.close()
    p.unlink(missing_ok=True)


def test_migration_creates_projects_table(db):
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
    ).fetchall()
    assert len(rows) == 1
    # tasks has project_id column
    cols = [r["name"] for r in db.conn.execute("PRAGMA table_info(tasks)").fetchall()]
    assert "project_id" in cols
    assert "sprint_id" in cols
    assert "notes" in cols


def test_get_or_create_project_idempotent(db):
    a = db.get_or_create_project("pomban")
    b = db.get_or_create_project("pomban")
    assert a.id == b.id
    assert a.color  # auto-colored


def test_list_tasks_filter_sentinel(db):
    proj = db.get_or_create_project("pomban")
    db.add_task("with project", project_id=proj.id)
    db.add_task("orphan")
    # Default: no filter — both visible
    assert len(db.list_tasks()) == 2
    # Filter to project
    pid_tasks = db.list_tasks(project_filter=proj.id)
    assert len(pid_tasks) == 1
    assert pid_tasks[0].project_id == proj.id
    # Inbox only (project_id IS NULL)
    inbox = db.list_tasks(project_filter=None)
    assert len(inbox) == 1
    assert inbox[0].title == "orphan"


def test_archive_hides_from_default_list(db):
    p = db.add_project("temp")
    assert p in db.list_projects()
    db.archive_project(p.id)
    assert p not in db.list_projects()
    assert any(x.id == p.id for x in db.list_projects(include_archived=True))


def test_delete_project_moves_tasks_to_inbox(db):
    p = db.get_or_create_project("zap")
    t = db.add_task("doomed", project_id=p.id)
    db.delete_project(p.id, move_tasks_to_inbox=True)
    survivor = db.get_task(t.id)
    assert survivor.project_id is None


def test_app_parser_handles_at_project_and_tilde_estimate():
    # Pure parser test — we don't need full app, just verify add_task_from_input logic
    # by replicating the parsing inline. Real integration covered by smoke test.
    from pomban.app import PomodoroApp

    p = Path(tempfile.mktemp(suffix=".db"))
    d = DB(p)
    # Build an app shell with no Textual mount
    app = PomodoroApp(db=d)
    task = app.add_task_from_input("Wire OAuth @work !v1.0 ~5 #backend #urgent")
    assert task.title == "Wire OAuth"
    assert task.estimated_pomodoros == 5
    assert "backend" in task.tags and "urgent" in task.tags
    proj = d.get_project(task.project_id)
    assert proj.name == "work"
    sp = d.get_sprint(task.sprint_id)
    assert sp.name == "v1.0"
    assert sp.project_id == proj.id
    d.close()
    p.unlink(missing_ok=True)


def test_migration_preserves_v2_tasks():
    """Verify v2 → SCHEMA_VERSION migration keeps existing rows and adds NULL project_id."""
    p = Path(tempfile.mktemp(suffix=".db"))
    raw = sqlite3.connect(str(p))
    raw.executescript("""
        CREATE TABLE tasks (
          id INTEGER PRIMARY KEY, title TEXT NOT NULL,
          status TEXT NOT NULL, tags TEXT DEFAULT '',
          estimated_pomodoros INTEGER DEFAULT 0, position INTEGER DEFAULT 0,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE sessions (id INTEGER PRIMARY KEY, kind TEXT, started_at TEXT NOT NULL,
          ended_at TEXT, planned_seconds INTEGER NOT NULL, actual_seconds INTEGER DEFAULT 0,
          completed INTEGER DEFAULT 0, interruption_count INTEGER DEFAULT 0);
        CREATE TABLE session_tasks (session_id INTEGER, task_id INTEGER,
          completed_during_session INTEGER DEFAULT 0,
          PRIMARY KEY (session_id, task_id));
        CREATE TABLE config_kv (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE interruptions (id INTEGER PRIMARY KEY, session_id INTEGER,
          at TEXT NOT NULL, reason TEXT DEFAULT '');
        INSERT INTO tasks (title, status, created_at, updated_at)
            VALUES ('Old task', 'todo', '2024-01-01', '2024-01-01');
        PRAGMA user_version = 2;
    """)
    raw.commit()
    raw.close()
    d = DB(p)
    v = d.conn.execute("PRAGMA user_version").fetchone()[0]
    assert v == SCHEMA_VERSION
    survivors = d.list_tasks()
    assert len(survivors) == 1
    assert survivors[0].title == "Old task"
    assert survivors[0].project_id is None
    d.close()
    p.unlink(missing_ok=True)
