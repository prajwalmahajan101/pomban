import tempfile
from pathlib import Path

from pomodoro.core.db import DB
from pomodoro.core.filter_state import FilterState
from pomodoro.core.filters import ProjectFilter


def _db(td):
    return DB(Path(td) / "f.db")


def test_defaults_all_and_no_sprint():
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        fs = FilterState(db)
        assert fs.project.is_all and fs.sprint_id is None
        db.close()


def test_set_project_persists_across_reopen():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "f.db"
        db = DB(path)
        p = db.add_project("Acme")
        FilterState(db).set_project(ProjectFilter.project(p.id))
        db.close()
        fs2 = FilterState(DB(path))
        assert fs2.project.is_project and fs2.project.project_id == p.id


def test_set_project_to_all_clears_active_sprint():
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        p = db.add_project("Acme")
        sp = db.get_or_create_sprint(p.id, "v1")
        fs = FilterState(db)
        fs.set_project(ProjectFilter.project(p.id))
        fs.set_sprint(sp.id)
        assert fs.sprint_id == sp.id
        fs.set_project(ProjectFilter.all())  # scope None → sprint invalid
        assert fs.sprint_id is None
        db.close()


def test_switching_project_clears_mismatched_sprint():
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        a, b = db.add_project("A"), db.add_project("B")
        spa = db.get_or_create_sprint(a.id, "v1")
        fs = FilterState(db)
        fs.set_project(ProjectFilter.project(a.id))
        fs.set_sprint(spa.id)
        fs.set_project(ProjectFilter.project(b.id))  # sprint belongs to A → cleared
        assert fs.sprint_id is None
        db.close()


def test_label_and_color():
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        p = db.add_project("Acme")
        fs = FilterState(db)
        fs.set_project(ProjectFilter.project(p.id))
        assert fs.project_label() == "Acme"
        assert fs.project_color() == p.color
        fs.set_project(ProjectFilter.inbox())
        assert fs.project_label() == "Inbox"
        fs.set_project(ProjectFilter.all())
        assert fs.project_label() is None and fs.project_color() == "white"
        db.close()
