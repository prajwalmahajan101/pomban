import tempfile
from pathlib import Path

import pytest

from pomodoro.app import PomodoroApp
from pomodoro.core.db import DB
from pomodoro.screens.dashboard import DashboardScreen
from pomodoro.screens.stats import StatsScreen


async def wait_for(pilot, screen_cls):
    for _ in range(40):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(type(pilot.app.screen))


@pytest.mark.asyncio
async def test_switch_to_stats_screen():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "s.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("3")
            await wait_for(pilot, StatsScreen)
        db.close()


@pytest.mark.asyncio
async def test_pause_during_focus_logs_interruption():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "s.db")
        db.add_task("Tracked")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await wait_for(pilot, DashboardScreen)
            from textual.widgets import ListView

            lv = scr.query_one("#task-list", ListView)
            lv.focus()
            lv.index = 0
            await pilot.press("enter")
            await pilot.pause()
            sid = app.current_session_id
            assert sid is not None
            # pause
            await pilot.press("s")
            await pilot.pause()
            assert not app.engine.running
            row = db.conn.execute(
                "SELECT interruption_count FROM sessions WHERE id=?", (sid,)
            ).fetchone()
            assert row["interruption_count"] == 1
        db.close()
