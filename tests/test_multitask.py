import tempfile
import time
from pathlib import Path

import pytest

from pomodoro.app import PomodoroApp
from pomodoro.core.db import DB
from pomodoro.core.timer_engine import Phase
from pomodoro.screens.dashboard import DashboardScreen
from pomodoro.screens.kanban import KanbanScreen


async def wait_for(pilot, screen_cls):
    for _ in range(40):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(f"Screen {screen_cls.__name__} never active: {type(pilot.app.screen)}")


@pytest.mark.asyncio
async def test_visual_mode_toggles_selection():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        t = db.add_task("Pick me")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("2")
            scr = await wait_for(pilot, KanbanScreen)
            await pilot.pause()
            await pilot.press("v")
            await pilot.pause()
            assert scr.visual_mode is True
            await pilot.press("space")
            await pilot.pause()
            assert t.id in scr.selected_ids
            await pilot.press("space")
            await pilot.pause()
            assert t.id not in scr.selected_ids
        db.close()


@pytest.mark.asyncio
async def test_start_focus_on_many_creates_one_session_three_links():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        tasks = [db.add_task(f"T{i}") for i in range(3)]
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            app.start_focus_on_many(tasks)
            await pilot.pause()
            assert app.engine.phase == Phase.FOCUS
            sid = app.current_session_id
            assert sid is not None
            n_links = db.conn.execute(
                "SELECT COUNT(*) AS n FROM session_tasks WHERE session_id=?", (sid,)
            ).fetchone()["n"]
            assert n_links == 3
            n_sessions = db.conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()["n"]
            assert n_sessions == 1
            for t in tasks:
                assert db.get_task(t.id).status == "doing"
        db.close()


@pytest.mark.asyncio
async def test_multi_complete_marks_only_chosen_subset():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        tasks = [db.add_task(f"T{i}") for i in range(3)]
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            app.start_focus_on_many(tasks)
            await pilot.pause()
            sid = app.current_session_id
            # Drive the focus phase to completion so the engine awaits a decision
            # (this is the state _finalize_multi_complete is invoked from).
            app.engine.tick(time.monotonic() + app.engine.settings.focus_seconds + 5)
            assert app.engine.awaiting_decision
            # Mark only the first and third done.
            app._finalize_multi_complete(sid, 100, [tasks[0].id, tasks[2].id])
            await pilot.pause()
            assert db.get_task(tasks[0].id).status == "done"
            assert db.get_task(tasks[2].id).status == "done"
            assert db.get_task(tasks[1].id).status == "doing"
            # The unfinished task stays in the active set; the session advanced.
            assert [t.id for t in app.active_tasks] == [tasks[1].id]
            assert app.engine.phase == Phase.SHORT_BREAK
        db.close()


@pytest.mark.asyncio
async def test_tab_cycles_chip_without_touching_engine():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        tasks = [db.add_task(f"T{i}") for i in range(2)]
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await wait_for(pilot, DashboardScreen)
            app.start_focus_on_many(tasks)
            await pilot.pause()
            phase_before = app.engine.phase
            running_before = app.engine.running
            remaining_before = app.engine.remaining
            assert app.active_chip_index == 0
            scr.action_cycle_active_chip()
            assert app.active_chip_index == 1
            scr.action_cycle_active_chip()
            assert app.active_chip_index == 0
            assert app.engine.phase == phase_before
            assert app.engine.running == running_before
            assert app.engine.remaining == remaining_before
        db.close()
