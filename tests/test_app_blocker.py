"""Pilot tests for the M4 blocker capture binding (`b` during focus)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.screens.blocker import BlockerModal
from pomban.screens.dashboard import DashboardScreen


async def wait_for(pilot, screen_cls, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(
        f"Screen {screen_cls.__name__} never became active: {type(pilot.app.screen)}"
    )


@pytest.mark.asyncio
async def test_b_during_focus_logs_interruption_and_updates_chip():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "b.db")
        task = db.add_task("Deep work")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            app.start_focus_on(task)
            await pilot.pause()
            sid = app.current_session_id
            assert sid is not None

            await pilot.press("b")
            await wait_for(pilot, BlockerModal)
            await pilot.press("p", "i", "n", "g")
            await pilot.press("enter")
            await wait_for(pilot, DashboardScreen)

            assert db.count_today_interruptions() == 1
            row = db.conn.execute(
                "SELECT interruption_count FROM sessions WHERE id=?", (sid,)
            ).fetchone()
            assert row["interruption_count"] == 1
            # Chip is rendered via ContextHeader; assert via the helper output.
            from pomban.widgets.context_header import ContextHeader

            assert "⚠ 1 today" in ContextHeader._warn_segment(app)
        db.close()


@pytest.mark.asyncio
async def test_b_outside_focus_is_noop():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "b2.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("b")
            # No focus session → no modal, no interruption row.
            for _ in range(5):
                await pilot.pause()
                assert not isinstance(pilot.app.screen, BlockerModal)
            assert db.count_today_interruptions() == 0
        db.close()
