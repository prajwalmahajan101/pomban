"""ContextHeader: project + sprint progress strip on every AppScreen."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.core.filters import ProjectFilter
from pomban.screens.base import AppScreen
from pomban.widgets.context_header import ContextHeader


async def _wait_for_dashboard(pilot, app, max_pumps: int = 40) -> AppScreen:
    for _ in range(max_pumps):
        await pilot.pause()
        if isinstance(app.screen, AppScreen):
            return app.screen
    raise AssertionError("no AppScreen mounted")


def _header_text(scr: AppScreen) -> str:
    ch = scr.query_one("#context-header", ContextHeader)
    return str(ch.render())


@pytest.mark.asyncio
async def test_context_header_shows_all_when_no_filter():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await _wait_for_dashboard(pilot, app)
            text = _header_text(scr)
            assert "Project:" in text
            assert "All" in text
            assert "Sprint: —" in text
        db.close()


@pytest.mark.asyncio
async def test_context_header_updates_with_project_filter():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        proj = db.add_project("release-week", color="magenta")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await _wait_for_dashboard(pilot, app)
            app.set_project_filter(ProjectFilter.project(proj.id))
            await pilot.pause()
            text = _header_text(scr)
            assert "release-week" in text
        db.close()


@pytest.mark.asyncio
async def test_context_header_shows_sprint_progress_bar():
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
        t = db.add_task("ship", project_id=proj.id, sprint_id=sp.id)
        for _ in range(4):
            sid = db.start_session("focus", planned_seconds=1500, task_ids=[t.id])
            db.end_session(sid, actual_seconds=1500, completed=True)

        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await _wait_for_dashboard(pilot, app)
            app.set_project_filter(ProjectFilter.project(proj.id))
            app.set_active_sprint(sp.id)
            await pilot.pause()
            text = _header_text(scr)
            assert "4/10" in text
            assert text.count("▮") == 5  # round(12 * 40 / 100) = 5
            assert "rollout" in text
        db.close()


@pytest.mark.asyncio
async def test_context_header_no_target_message():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        proj = db.add_project("p")
        today = dt.date.today()
        sp = db.add_sprint(
            project_id=proj.id,
            name="loose",
            start_date=today.isoformat(),
            end_date=(today + dt.timedelta(days=7)).isoformat(),
            pomodoro_target=0,
            status="active",
        )

        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            scr = await _wait_for_dashboard(pilot, app)
            app.set_project_filter(ProjectFilter.project(proj.id))
            app.set_active_sprint(sp.id)
            await pilot.pause()
            text = _header_text(scr)
            assert "no target" in text
            assert "▮" not in text
        db.close()
