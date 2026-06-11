from pomban.core.db import _NO
from pomban.core.filters import ProjectFilter


def test_all_filter():
    pf = ProjectFilter.all()
    assert pf.is_all and not pf.is_inbox and not pf.is_project
    assert pf.scoped_project_id is None
    assert pf.for_db() is _NO
    assert pf.to_kv() is None


def test_inbox_filter():
    pf = ProjectFilter.inbox()
    assert pf.is_inbox
    assert pf.scoped_project_id is None
    assert pf.for_db() is None  # project_id IS NULL
    assert pf.to_kv() == "inbox"


def test_project_filter():
    pf = ProjectFilter.project(7)
    assert pf.is_project
    assert pf.scoped_project_id == 7
    assert pf.for_db() == 7
    assert pf.to_kv() == "7"


def test_roundtrip_kv():
    for pf in (ProjectFilter.all(), ProjectFilter.inbox(), ProjectFilter.project(3)):
        assert ProjectFilter.from_kv(pf.to_kv()) == pf


def test_from_kv_tolerates_legacy_inbox_sentinel():
    assert ProjectFilter.from_kv("-2") == ProjectFilter.inbox()


def test_from_kv_garbage_is_all():
    assert ProjectFilter.from_kv("not-an-int") == ProjectFilter.all()
    assert ProjectFilter.from_kv(None) == ProjectFilter.all()


def test_equality_enables_cycle_index():
    cycle = [ProjectFilter.all(), ProjectFilter.project(1), ProjectFilter.inbox()]
    assert cycle.index(ProjectFilter.project(1)) == 1
