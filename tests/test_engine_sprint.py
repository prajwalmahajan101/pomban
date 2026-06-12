"""Unit tests for PombanEngine's sprint surface (M3).

Exercises ``check_sprint_target_hit`` boundary logic and the
``create_sprint_for_project`` / ``close_sprint`` wrappers without a
Textual pilot.
"""

from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from pomban.core.db import DB
from pomban.core.engine import PombanEngine
from pomban.core.filter_state import FilterState


@pytest.fixture
def env():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "es.db")
        filters = FilterState(db)
        engine = PombanEngine(db=db, filters=filters)
        yield engine, db, filters
        db.close()


def _make_sprint(db: DB, target: int) -> tuple[int, int, int]:
    project = db.add_project("P")
    start = date.today().isoformat()
    end = (date.today() + timedelta(days=14)).isoformat()
    sprint = db.add_sprint(project.id, "S", start, end, pomodoro_target=target)
    db.activate_sprint(sprint.id)
    task = db.add_task("T", project_id=project.id, sprint_id=sprint.id)
    return project.id, sprint.id, task.id


def _log_completed_focus(db: DB, task_id: int) -> int:
    sid = db.start_session("focus", planned_seconds=300, task_ids=[task_id])
    db.end_session(sid, actual_seconds=300, completed=True)
    return sid


# ---------- create / close ----------


def test_create_sprint_for_project_activates_new_sprint(env):
    engine, db, _filters = env
    project = db.add_project("Demo")
    sp = engine.create_sprint_for_project(project.id)
    assert sp.status == "active"
    assert sp.project_id == project.id
    # Auto-name "Sprint 1" since none existed
    assert sp.name == "Sprint 1"


def test_create_sprint_deactivates_sibling(env):
    engine, db, _filters = env
    project = db.add_project("Demo")
    first = engine.create_sprint_for_project(project.id)
    second = engine.create_sprint_for_project(project.id)
    assert db.get_sprint(first.id).status == "planned"
    assert db.get_sprint(second.id).status == "active"


def test_close_sprint_marks_completed_and_stores_retro(env):
    engine, db, _filters = env
    _, sprint_id, _ = _make_sprint(db, target=2)
    engine.close_sprint(sprint_id, "went well")
    sp = db.get_sprint(sprint_id)
    assert sp.status == "completed"
    assert sp.retrospective == "went well"


# ---------- check_sprint_target_hit ----------


def test_target_hit_when_no_active_sprint_returns_none(env):
    engine, db, _filters = env
    project = db.add_project("P")
    task = db.add_task("T", project_id=project.id)
    sid = _log_completed_focus(db, task.id)
    assert engine.check_sprint_target_hit(sid) is None


def test_target_hit_with_target_zero_returns_none(env):
    engine, db, filters = env
    _, sprint_id, task_id = _make_sprint(db, target=0)
    filters.set_sprint(sprint_id)
    sid = _log_completed_focus(db, task_id)
    assert engine.check_sprint_target_hit(sid) is None


def test_target_hit_exactly_at_target_fires(env):
    engine, db, filters = env
    _, sprint_id, task_id = _make_sprint(db, target=1)
    filters.set_sprint(sprint_id)
    sid = _log_completed_focus(db, task_id)
    sp = engine.check_sprint_target_hit(sid)
    assert sp is not None
    assert sp.id == sprint_id


def test_target_hit_fires_once_not_on_subsequent_sessions(env):
    engine, db, filters = env
    _, sprint_id, task_id = _make_sprint(db, target=1)
    filters.set_sprint(sprint_id)
    # Called the way the app calls it: immediately after each session finalizes.
    first = _log_completed_focus(db, task_id)
    assert engine.check_sprint_target_hit(first) is not None
    second = _log_completed_focus(db, task_id)
    assert engine.check_sprint_target_hit(second) is None


def test_target_hit_ignores_session_not_in_sprint(env):
    engine, db, filters = env
    _, sprint_id, _ = _make_sprint(db, target=1)
    filters.set_sprint(sprint_id)
    other = db.add_task("Other")  # No sprint
    sid = _log_completed_focus(db, other.id)
    assert engine.check_sprint_target_hit(sid) is None


def test_target_hit_ignores_incomplete_session(env):
    engine, db, filters = env
    _, sprint_id, task_id = _make_sprint(db, target=1)
    filters.set_sprint(sprint_id)
    sid = db.start_session("focus", planned_seconds=300, task_ids=[task_id])
    db.end_session(sid, actual_seconds=10, completed=False)
    assert engine.check_sprint_target_hit(sid) is None
