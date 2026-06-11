import tempfile
from pathlib import Path

import pytest

from pomban.core.db import DB


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as td:
        d = DB(Path(td) / "k.db")
        yield d
        d.close()


def test_move_task_changes_status(db):
    t = db.add_task("A")
    db.move_task(t.id, "doing")
    assert db.get_task(t.id).status == "doing"


def test_move_task_appends_to_end_of_column(db):
    a = db.add_task("A")
    b = db.add_task("B")
    c = db.add_task("C")
    db.move_task(a.id, "doing")
    db.move_task(b.id, "doing")
    db.move_task(c.id, "doing")
    rows = db.list_tasks(status="doing")
    assert [t.title for t in rows] == ["A", "B", "C"]


def test_swap_positions_reorders(db):
    a = db.add_task("A")
    b = db.add_task("B")
    rows = db.list_tasks(status="todo")
    assert [t.title for t in rows] == ["A", "B"]
    db.swap_positions(a.id, b.id)
    rows = db.list_tasks(status="todo")
    assert [t.title for t in rows] == ["B", "A"]


def test_list_tasks_by_status_groups_correctly(db):
    a = db.add_task("A")
    db.add_task("B")
    db.move_task(a.id, "doing")
    groups = db.list_tasks_by_status()
    assert [t.title for t in groups["todo"]] == ["B"]
    assert [t.title for t in groups["doing"]] == ["A"]
    assert groups["done"] == []
