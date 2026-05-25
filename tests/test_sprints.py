"""Tests for Phase O: sprints, !sprint inline syntax, activate-only-one invariant, burndown."""
from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from pomodoro.app import PomodoroApp
from pomodoro.core.db import DB


@pytest.fixture
def db():
    p = Path(tempfile.mktemp(suffix=".db"))
    d = DB(p)
    yield d
    d.close()
    p.unlink(missing_ok=True)


def test_add_and_get_sprint(db):
    sp = db.add_sprint(None, "v1.0", "2026-05-01", "2026-05-15", goal="ship", pomodoro_target=40)
    again = db.get_sprint(sp.id)
    assert again.name == "v1.0" and again.pomodoro_target == 40 and again.goal == "ship"


def test_one_active_sprint_per_project(db):
    proj = db.get_or_create_project("p1")
    a = db.add_sprint(proj.id, "a", "2026-01-01", "2026-01-14")
    b = db.add_sprint(proj.id, "b", "2026-02-01", "2026-02-14")
    db.activate_sprint(a.id)
    db.activate_sprint(b.id)
    # a should no longer be active
    assert db.get_sprint(a.id).status == "planned"
    assert db.get_sprint(b.id).status == "active"


def test_bang_sprint_inline_parser_auto_creates_shell():
    p = Path(tempfile.mktemp(suffix=".db"))
    d = DB(p)
    app = PomodoroApp(db=d)
    t = app.add_task_from_input("Plan release @work !v2.0 ~3")
    assert t.sprint_id is not None
    sp = d.get_sprint(t.sprint_id)
    assert sp.name == "v2.0"
    assert sp.status == "planned"   # auto-created shell, not active yet
    # 14-day default window
    end = date.fromisoformat(sp.end_date)
    start = date.fromisoformat(sp.start_date)
    assert (end - start).days == 14
    d.close()
    p.unlink(missing_ok=True)


def test_burndown_returns_series(db):
    sp = db.add_sprint(None, "demo", "2026-01-01", "2026-01-07", pomodoro_target=14)
    bd = db.sprint_burndown(sp.id)
    assert len(bd["days"]) == 7
    assert bd["target"] == 14
    assert bd["completed"] == 0
    # Ideal series goes from target down to 0 linearly
    assert bd["ideal_series"][0] == 14
    assert bd["ideal_series"][-1] == 0


def test_delete_sprint_releases_tasks(db):
    proj = db.get_or_create_project("p")
    sp = db.add_sprint(proj.id, "x", "2026-01-01", "2026-01-14")
    t = db.add_task("in sprint", project_id=proj.id, sprint_id=sp.id)
    db.delete_sprint(sp.id)
    survivor = db.get_task(t.id)
    assert survivor.sprint_id is None
