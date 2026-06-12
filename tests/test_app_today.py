"""Pilot test for the M4 Today digest screen (`7`)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.today import TodayScreen


async def wait_for(pilot, screen_cls, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(
        f"Screen {screen_cls.__name__} never became active: {type(pilot.app.screen)}"
    )


@pytest.mark.asyncio
async def test_seven_opens_today_and_renders_panels():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "t.db")
        project = db.add_project("Demo")
        task = db.add_task("Polish slides", project_id=project.id)
        # Seed a completed focus session today.
        sid = db.start_session("focus", planned_seconds=300, task_ids=[task.id])
        db.end_session(sid, actual_seconds=300, completed=True)
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("7")
            screen = await wait_for(pilot, TodayScreen)

            from textual.widgets import Static

            sessions = screen.query_one("#today-sessions", Static)
            assert "Completed focus" in str(sessions.render())
            assert "1" in str(sessions.render())

            top = screen.query_one("#today-top-tasks", Static)
            assert "Polish slides" in str(top.render())

            by_project = screen.query_one("#today-by-project", Static)
            assert "Demo" in str(by_project.render())
        db.close()


@pytest.mark.asyncio
async def test_today_screen_empty_states():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "te.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("7")
            screen = await wait_for(pilot, TodayScreen)
            from textual.widgets import Static

            top = screen.query_one("#today-top-tasks", Static)
            assert "No focus sessions yet" in str(top.render())
            by_project = screen.query_one("#today-by-project", Static)
            assert "No focus sessions today" in str(by_project.render())
        db.close()
