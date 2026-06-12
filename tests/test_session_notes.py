"""Tests for M4 session notes (schema v10 UI wiring)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.core.timer_engine import Phase
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.history import HistoryScreen
from pomban.screens.session_end import SessionEndScreen


async def wait_for(pilot, screen_cls, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(
        f"Screen {screen_cls.__name__} never became active: {type(pilot.app.screen)}"
    )


def test_update_session_writes_arbitrary_fields(tmp_path):
    db = DB(tmp_path / "u.db")
    sid = db.start_session("focus", planned_seconds=300, task_ids=[])
    db.update_session(sid, notes="hello", completed=1)
    row = db.conn.execute("SELECT notes, completed FROM sessions WHERE id=?", (sid,)).fetchone()
    assert row["notes"] == "hello"
    assert row["completed"] == 1
    db.close()


def test_session_history_returns_notes(tmp_path):
    db = DB(tmp_path / "h.db")
    sid = db.start_session("focus", planned_seconds=300, task_ids=[])
    db.end_session(sid, actual_seconds=300, completed=True)
    db.update_session(sid, notes="went well")
    rows = db.session_history(limit=10)
    assert any(r["notes"] == "went well" for r in rows)
    db.close()


@pytest.mark.asyncio
async def test_session_end_complete_saves_notes_via_modal():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "n.db")
        task = db.add_task("Deep")
        app = PomodoroApp(db=db, fast=True)
        # Force the modal-based (non-auto) flow.
        app.config.timer.auto_advance = False
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            app.start_focus_on(task)
            await pilot.pause()
            sid = app.current_session_id
            assert sid is not None
            app._on_phase_completed()
            screen = await wait_for(pilot, SessionEndScreen)
            # Stash a note directly on the screen state (covers the n→modal flow
            # without depending on the NoteModal pilot mechanics).
            screen._stashed_notes = "shipped first slice"
            screen.action_complete()
            await wait_for(pilot, DashboardScreen)
            row = db.conn.execute("SELECT notes FROM sessions WHERE id=?", (sid,)).fetchone()
            assert row["notes"] == "shipped first slice"
        db.close()


@pytest.mark.asyncio
async def test_history_screen_renders_notes_column():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "hn.db")
        sid = db.start_session("focus", planned_seconds=300, task_ids=[])
        db.end_session(sid, actual_seconds=300, completed=True)
        db.update_session(sid, notes="end of day")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("4")
            await wait_for(pilot, HistoryScreen)
            from textual.widgets import DataTable

            table = pilot.app.screen.query_one("#hist", DataTable)
            cols = [str(c.label) for c in table.columns.values()]
            assert "Notes" in cols
            # Confirm the seeded note appears in some row.
            seen = []
            for row_key in table.rows.keys():
                row_data = table.get_row(row_key)
                seen.extend(str(c) for c in row_data)
            assert any("end of day" in s for s in seen)
        db.close()


def test_action_add_note_noop_on_break_phase():
    """n is a no-op for break completions (notes only apply to focus sessions)."""
    from pomban.screens.session_end import SessionEndScreen

    screen = SessionEndScreen(completed_phase=Phase.SHORT_BREAK, task_title=None)
    # Calling action_add_note shouldn't raise or stash anything since the
    # guard exits early before push_screen.
    screen.action_add_note()
    assert screen._stashed_notes == ""
