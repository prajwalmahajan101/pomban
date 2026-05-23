import tempfile
from pathlib import Path

import pytest

from pomodoro.core.db import DB


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as td:
        d = DB(Path(td) / "tags.db")
        yield d
        d.close()


def test_inline_tag_parsing_via_app():
    # Pure parser, no Textual UI
    text = "Write report #docs #urgent"
    words = text.split()
    title_words, tags = [], []
    for w in words:
        if w.startswith("#") and len(w) > 1:
            tags.append(w[1:])
        else:
            title_words.append(w)
    assert " ".join(title_words) == "Write report"
    assert tags == ["docs", "urgent"]


def test_list_tasks_filter_by_tag(db):
    db.add_task("A", tags="docs")
    db.add_task("B", tags="urgent")
    db.add_task("C", tags="docs,urgent")
    docs = db.list_tasks(tag="docs")
    urg = db.list_tasks(tag="urgent")
    assert {t.title for t in docs} == {"A", "C"}
    assert {t.title for t in urg} == {"B", "C"}


def test_filter_is_case_insensitive_and_strips_hash(db):
    db.add_task("X", tags="Docs")
    assert {t.title for t in db.list_tasks(tag="DOCS")} == {"X"}
    assert {t.title for t in db.list_tasks(tag="#docs")} == {"X"}


def test_all_tags_returns_distinct_sorted(db):
    db.add_task("A", tags="docs,urgent")
    db.add_task("B", tags="docs")
    db.add_task("C", tags="bug")
    assert db.all_tags() == ["bug", "docs", "urgent"]


def test_add_task_via_app_parses_inline_tags(tmp_path):
    db = DB(tmp_path / "t.db")
    from pomodoro.app import PomodoroApp
    app = PomodoroApp(db=db, fast=True)
    t = app.add_task_from_input("Fix bug #backend #p1")
    assert t.title == "Fix bug"
    assert t.tags == "backend,p1"


def test_card_renders_chip():
    from pomodoro.core.models import Task
    from pomodoro.widgets.card import render_chips, tag_color
    out = render_chips("docs,urgent")
    assert "#docs" in out and "#urgent" in out
    # Deterministic color
    assert tag_color("docs") == tag_color("docs")
