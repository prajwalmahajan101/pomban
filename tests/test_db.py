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
