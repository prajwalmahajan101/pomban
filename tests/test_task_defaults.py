import tempfile
from pathlib import Path

import pytest

from pomodoro.app import PomodoroApp
from pomodoro.core.db import DB
from pomodoro.core.filters import ProjectFilter


@pytest.fixture
def app():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "t.db")
        a = PomodoroApp(db=db, fast=True)
        yield a
        db.close()


def test_new_task_defaults_to_active_sprint(app):
    # Regression: a new task created under a sprint filter used to get sprint_id=None
    # and vanish from the filtered board. It should inherit the active sprint.
    proj = app.db.get_or_create_project("work")
    sp = app.db.get_or_create_sprint(proj.id, "v1")
    app.set_project_filter(ProjectFilter.project(proj.id))
    app.active_sprint_id = sp.id

    t = app.add_task_from_input("ship it")
    assert t.project_id == proj.id
    assert t.sprint_id == sp.id


def test_explicit_project_token_does_not_inherit_filter_sprint(app):
    # If the user types @otherproject, don't apply the (mismatched) filter sprint.
    work = app.db.get_or_create_project("work")
    sp = app.db.get_or_create_sprint(work.id, "v1")
    app.set_project_filter(ProjectFilter.project(work.id))
    app.active_sprint_id = sp.id

    t = app.add_task_from_input("side task @hobby")
    assert app.db.get_project(t.project_id).name == "hobby"
    assert t.sprint_id is None


def test_no_sprint_filter_means_no_sprint(app):
    proj = app.db.get_or_create_project("work")
    app.set_project_filter(ProjectFilter.project(proj.id))
    t = app.add_task_from_input("plain")
    assert t.sprint_id is None
