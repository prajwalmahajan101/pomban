"""Tests for the kanban enhancements: due/priority schema, card render, sort, search."""

import tempfile
from pathlib import Path

import pytest

from pomodoro.app import PomodoroApp
from pomodoro.core.config import Config
from pomodoro.core.db import DB, SCHEMA_VERSION
from pomodoro.core.models import Task
from pomodoro.screens.kanban import _matches_query, _sort_key
from pomodoro.widgets.card import render_due, render_priority


def _db(td):
    return DB(Path(td) / "k.db")


# ---------------- migration v9: due_date + priority ----------------


def test_migration_v9_adds_columns_with_defaults():
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        assert db.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        t = db.add_task("X")
        assert t.due_date == "" and t.priority == 0
        db.close()


def test_add_task_with_due_and_priority_round_trip():
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        t = db.add_task("Ship", due_date="2026-06-01", priority=3)
        got = db.get_task(t.id)
        assert got.due_date == "2026-06-01" and got.priority == 3
        db.close()


def test_update_task_sets_due_and_priority():
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        t = db.add_task("Edit me")
        db.update_task(t.id, due_date="2026-05-30", priority=2)
        got = db.get_task(t.id)
        assert got.due_date == "2026-05-30" and got.priority == 2
        db.close()


def test_migration_idempotent_on_reopen():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "k.db"
        db = DB(path)
        db.add_task("keep me", due_date="2026-07-01", priority=1)
        db.close()
        # Reopen: migration must not re-run the ALTERs or raise, version stays put.
        db2 = DB(path)
        assert db2.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        got = db2.list_tasks()[0]
        assert got.due_date == "2026-07-01" and got.priority == 1
        db2.close()


# ---------------- card render: priority + due ----------------


def test_render_priority_glyph():
    assert render_priority(0) == ""
    out = render_priority(3)
    assert "▲" in out and "red" in out


def test_render_priority_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert render_priority(3) == "▲"  # plain glyph, no markup


def test_render_due_overdue_and_future():
    overdue = render_due("2000-01-01")
    assert "⏰" in overdue and "red" in overdue
    future = render_due("2999-12-31")
    assert "⏰" in future and "dim" in future
    assert render_due("") == ""


def test_render_due_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert render_due("2000-01-01").startswith("(!)")
    assert render_due("2999-12-31").startswith("~")


# ---------------- column sort ----------------


def test_sort_key_priority_then_due_then_position():
    tasks = [
        Task(id=1, title="a", priority=0, position=0),
        Task(id=2, title="b", priority=3, position=5),
        Task(id=3, title="c", priority=0, due_date="2026-06-01", position=1),
        Task(id=4, title="d", priority=0, due_date="2026-05-01", position=2),
    ]
    order = [t.id for t in sorted(tasks, key=_sort_key)]
    # priority 3 first; then dated (earlier due first); then undated by position
    assert order == [2, 4, 3, 1]


# ---------------- card detail view + editor due/priority ----------------


@pytest.mark.asyncio
async def test_kanban_open_detail_then_edit():
    from pomodoro.screens.card_detail import CardDetailScreen
    from pomodoro.screens.edit_task import EditTaskModal

    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        db.add_task("Read a book")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test() as pilot:
            await pilot.press("2")  # -> kanban
            await pilot.pause()
            await pilot.press("i")  # open detail
            await pilot.pause()
            assert isinstance(app.screen, CardDetailScreen)
            await pilot.press("e")  # -> editor
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, EditTaskModal)
        db.close()


@pytest.mark.asyncio
async def test_on_task_edited_persists_due_and_priority():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        t = db.add_task("Edit")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test():
            app._on_task_edited(
                t.id,
                {
                    "title": "Edit",
                    "tags": "",
                    "estimate": 0,
                    "project": "",
                    "due_date": "2026-06-02",
                    "priority": 2,
                },
            )
            got = db.get_task(t.id)
            assert got.due_date == "2026-06-02" and got.priority == 2
        db.close()


# ---------------- search / filter ----------------


def test_matches_query():
    t = Task(id=1, title="Write the Report", tags="urgent,docs")
    assert _matches_query(t, "")  # empty matches all
    assert _matches_query(t, "report")  # case-insensitive title substring
    assert _matches_query(t, "#urgent")  # tag match
    assert _matches_query(t, "urg")  # bare substring hits tags too
    assert not _matches_query(t, "#missing")
    assert not _matches_query(t, "zzz")


def test_kanban_section_loads_and_ignores_unknown(tmp_path):
    from pomodoro.core.config import load

    p = tmp_path / "c.toml"
    p.write_text("[kanban]\nwip_doing = 3\nbogus = 1\n")
    cfg = load(p)
    assert cfg.kanban.wip_doing == 3  # known key parsed; unknown 'bogus' dropped


@pytest.mark.asyncio
async def test_kanban_search_filters_column_tasks():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        db.add_task("write report", tags="urgent")
        db.add_task("buy milk")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause()
            kb = app.screen
            kb.search_query = "#urgent"
            assert [t.title for t in kb._column_tasks(0)] == ["write report"]
            kb.search_query = ""
            assert len(kb._column_tasks(0)) == 2
        db.close()


# ---------------- WIP limits ----------------


@pytest.mark.asyncio
async def test_kanban_wip_overflow_flags_column():
    from pomodoro.core.config import KanbanSection

    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        db.add_task("a")
        db.add_task("b")
        cfg = Config()
        cfg.kanban = KanbanSection(wip_todo=1)
        app = PomodoroApp(db=db, fast=True, config=cfg)
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause()
            assert app.screen.query_one("#col-todo").has_class("-over-wip")
        db.close()


# ---------------- bulk actions (visual mode) ----------------


@pytest.mark.asyncio
async def test_kanban_bulk_complete():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        t1 = db.add_task("one")
        t2 = db.add_task("two")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause()
            kb = app.screen
            kb.visual_mode = True
            kb.selected_ids = {t1.id, t2.id}
            kb.action_complete_card()
            assert db.get_task(t1.id).status == "done"
            assert db.get_task(t2.id).status == "done"
        db.close()


@pytest.mark.asyncio
async def test_kanban_bulk_delete():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        t1 = db.add_task("one")
        t2 = db.add_task("two")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause()
            kb = app.screen
            kb.visual_mode = True
            kb.selected_ids = {t1.id, t2.id}
            kb.action_delete_card()
            assert db.list_tasks(include_done=True) == []
        db.close()


@pytest.mark.asyncio
async def test_kanban_bulk_tag():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        t1 = db.add_task("one")
        t2 = db.add_task("two")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test() as pilot:
            await pilot.press("2")
            await pilot.pause()
            kb = app.screen
            kb.visual_mode = True
            kb.selected_ids = {t1.id, t2.id}
            for t in kb._selected_tasks():
                kb._add_tag_to_task(t, "hot")
            assert "hot" in db.get_task(t1.id).tags
            assert "hot" in db.get_task(t2.id).tags
        db.close()
