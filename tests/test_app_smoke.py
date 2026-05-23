import tempfile
from pathlib import Path

import pytest
from textual.widgets import ListView

from pomodoro.app import PomodoroApp
from pomodoro.core.db import DB
from pomodoro.core.timer_engine import Phase
from pomodoro.screens.dashboard import DashboardScreen
from pomodoro.screens.session_end import SessionEndScreen


async def wait_for_dashboard(pilot) -> DashboardScreen:
    for _ in range(40):
        await pilot.pause()
        if isinstance(pilot.app.screen, DashboardScreen):
            return pilot.app.screen
    raise AssertionError(f"Dashboard never became active: {type(pilot.app.screen)}")


@pytest.mark.asyncio
async def test_app_mounts_and_keys_work():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "smoke.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for_dashboard(pilot)
            # Start timer
            await pilot.press("s")
            await pilot.pause()
            assert app.engine.phase == Phase.FOCUS
            assert app.engine.running
            # Pause
            await pilot.press("s")
            await pilot.pause()
            assert not app.engine.running
            # Reset
            await pilot.press("r")
            await pilot.pause()
            assert app.engine.phase == Phase.IDLE
        db.close()


@pytest.mark.asyncio
async def test_add_task_via_input():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "smoke.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for_dashboard(pilot)
            await pilot.press("n")
            await pilot.pause()
            for ch in "Test task":
                await pilot.press(ch if ch != " " else "space")
            await pilot.press("enter")
            await pilot.pause()
            tasks = db.list_tasks()
            assert len(tasks) == 1
            assert tasks[0].title == "Test task"
        db.close()


@pytest.mark.asyncio
async def test_focus_completion_shows_modal_and_complete_marks_done():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "smoke.db")
        task = db.add_task("Finish report")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await wait_for_dashboard(pilot)
            lv = scr.query_one("#task-list", ListView)
            lv.focus(); lv.index = 0
            await pilot.press("enter")
            await pilot.pause()
            assert app.engine.phase == Phase.FOCUS
            # Wait past 5s focus (fast mode) for completion modal
            await pilot.pause(delay=6.5)
            assert isinstance(app.screen, SessionEndScreen), type(app.screen)
            # Press 'c' to mark done
            await pilot.press("c")
            await pilot.pause(delay=0.5)
            # Modal dismissed, engine advanced to short_break, task is done.
            assert app.engine.phase == Phase.SHORT_BREAK
            assert db.get_task(task.id).status == "done"
            assert app.active_task is None
            # A completed focus session was logged.
            stats = db.stats_today()
            assert stats["sessions"] == 1
        db.close()


@pytest.mark.asyncio
async def test_focus_completion_extend_keeps_focus():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "smoke.db")
        db.add_task("Long task")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await wait_for_dashboard(pilot)
            lv = scr.query_one("#task-list", ListView)
            lv.focus(); lv.index = 0
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause(delay=6.5)
            assert isinstance(app.screen, SessionEndScreen)
            # Press '5' to extend by 5 minutes
            await pilot.press("5")
            await pilot.pause(delay=0.5)
            assert not isinstance(app.screen, SessionEndScreen)
            assert app.engine.phase == Phase.FOCUS
            assert app.engine.running
            assert app.engine.remaining >= 5 * 60 - 1
            assert app.active_task is not None
        db.close()
