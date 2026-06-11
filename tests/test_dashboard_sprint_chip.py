"""Dashboard A5: sprint-aware tasks pane title + timer sprint chip."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import pytest
from textual.widgets import Static

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.core.filters import ProjectFilter
from pomban.screens.dashboard import DashboardScreen
from pomban.widgets.timer_display import TimerDisplay


async def _wait_for_dashboard(pilot, app, max_pumps: int = 40) -> DashboardScreen:
    for _ in range(max_pumps):
        await pilot.pause()
        if isinstance(app.screen, DashboardScreen):
            return app.screen
    raise AssertionError("dashboard never mounted")


@pytest.mark.asyncio
async def test_pane_title_all_tasks_when_no_filter():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await _wait_for_dashboard(pilot, app)
            title = str(scr.query_one("#task-pane-title", Static).render())
            assert "All tasks" in title
        db.close()


@pytest.mark.asyncio
async def test_pane_title_project_queue_when_project_filtered():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        proj = db.add_project("release-week")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await _wait_for_dashboard(pilot, app)
            app.set_project_filter(ProjectFilter.project(proj.id))
            await pilot.pause()
            title = str(scr.query_one("#task-pane-title", Static).render())
            assert "Project queue" in title
        db.close()


@pytest.mark.asyncio
async def test_pane_title_sprint_queue_and_timer_chip_when_sprint_active():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        proj = db.add_project("api")
        today = dt.date.today()
        sp = db.add_sprint(
            project_id=proj.id,
            name="rollout",
            start_date=today.isoformat(),
            end_date=(today + dt.timedelta(days=7)).isoformat(),
            pomodoro_target=10,
            status="active",
        )

        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await _wait_for_dashboard(pilot, app)
            app.set_project_filter(ProjectFilter.project(proj.id))
            app.set_active_sprint(sp.id)
            await pilot.pause()
            title = str(scr.query_one("#task-pane-title", Static).render())
            assert "Sprint queue" in title

            td_widget = scr.query_one(TimerDisplay)
            assert "Sprint: rollout" in td_widget.sprint_chip
            assert "0/10" in td_widget.sprint_chip
            assert "Sprint: rollout" in td_widget.render()
        db.close()


@pytest.mark.asyncio
async def test_timer_chip_empty_without_sprint():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await _wait_for_dashboard(pilot, app)
            assert scr.query_one(TimerDisplay).sprint_chip == ""
        db.close()
