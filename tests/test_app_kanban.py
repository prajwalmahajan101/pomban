import tempfile
from pathlib import Path

import pytest

from pomodoro.app import PomodoroApp
from pomodoro.core.db import DB
from pomodoro.core.timer_engine import Phase
from pomodoro.screens.dashboard import DashboardScreen
from pomodoro.screens.kanban import KanbanScreen
from pomodoro.widgets.card import TaskCard


async def wait_for(pilot, screen_cls):
    for _ in range(40):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(f"Screen {screen_cls.__name__} never became active: {type(pilot.app.screen)}")


@pytest.mark.asyncio
async def test_switch_to_kanban_and_back():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("2")
            await wait_for(pilot, KanbanScreen)
            await pilot.press("1")
            await wait_for(pilot, DashboardScreen)
        db.close()


@pytest.mark.asyncio
async def test_kanban_renders_three_columns_with_counts():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        a = db.add_task("Aaa")
        b = db.add_task("Bbb")
        db.move_task(b.id, "doing")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("2")
            scr = await wait_for(pilot, KanbanScreen)
            await pilot.pause()
            # Count cards in each column
            todo_cards = list(scr.query_one("#body-todo").query(TaskCard))
            doing_cards = list(scr.query_one("#body-doing").query(TaskCard))
            assert len(todo_cards) == 1
            assert len(doing_cards) == 1
            assert todo_cards[0].task_data.title == "Aaa"
            assert doing_cards[0].task_data.title == "Bbb"
        db.close()


@pytest.mark.asyncio
async def test_kanban_move_card_right_with_shift_l():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        t = db.add_task("Movable")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("2")
            scr = await wait_for(pilot, KanbanScreen)
            await pilot.pause()
            assert scr.col == 0  # on To Do
            await pilot.press("shift+l")
            await pilot.pause()
            assert db.get_task(t.id).status == "doing"
            assert scr.col == 1
        db.close()


@pytest.mark.asyncio
async def test_kanban_start_focus_jumps_to_dashboard():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        db.add_task("Focus me")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("2")
            await wait_for(pilot, KanbanScreen)
            await pilot.pause()
            await pilot.press("s")  # start focus
            await wait_for(pilot, DashboardScreen)
            assert app.engine.phase == Phase.FOCUS
            assert app.active_task is not None
            assert app.active_task.title == "Focus me"
        db.close()


@pytest.mark.asyncio
async def test_kanban_new_card_input_adds_to_current_column():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "k.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("2")
            scr = await wait_for(pilot, KanbanScreen)
            await pilot.pause()
            # Move to "doing" column (col index 1)
            await pilot.press("l")
            await pilot.pause()
            assert scr.col == 1
            await pilot.press("n")
            await pilot.pause()
            for ch in "Quick":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            tasks = db.list_tasks_by_status()
            assert len(tasks["doing"]) == 1
            assert tasks["doing"][0].title == "Quick"
        db.close()
