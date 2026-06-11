"""A3: submit_new_task pushes ProjectPickerModal when context is missing."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.core.filters import ProjectFilter
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.project_picker import ProjectPickerModal


async def _wait_for_dashboard(pilot, app, max_pumps: int = 40) -> DashboardScreen:
    for _ in range(max_pumps):
        await pilot.pause()
        if isinstance(app.screen, DashboardScreen):
            return app.screen
    raise AssertionError("dashboard never mounted")


@pytest.mark.asyncio
async def test_submit_with_no_context_pushes_picker():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await _wait_for_dashboard(pilot, app)
            app.submit_new_task("Wire OAuth")
            await pilot.pause()
            assert isinstance(app.screen, ProjectPickerModal)
            assert db.list_tasks() == []
        db.close()


@pytest.mark.asyncio
async def test_picker_resolved_to_project_creates_task():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        proj = db.add_project("release-week")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await _wait_for_dashboard(pilot, app)
            app.submit_new_task("Wire OAuth")
            await pilot.pause()
            assert isinstance(app.screen, ProjectPickerModal)
            app.screen.dismiss(proj.id)
            await pilot.pause()
            tasks = db.list_tasks()
            assert len(tasks) == 1
            assert tasks[0].title == "Wire OAuth"
            assert tasks[0].project_id == proj.id
        db.close()


@pytest.mark.asyncio
async def test_picker_resolved_to_inbox_creates_unfiled_task():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await _wait_for_dashboard(pilot, app)
            app.submit_new_task("Email Dana")
            await pilot.pause()
            assert isinstance(app.screen, ProjectPickerModal)
            app.screen.dismiss(0)  # Inbox
            await pilot.pause()
            tasks = db.list_tasks()
            assert len(tasks) == 1
            assert tasks[0].project_id is None
        db.close()


@pytest.mark.asyncio
async def test_picker_dismissed_creates_nothing():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await _wait_for_dashboard(pilot, app)
            app.submit_new_task("hmm")
            await pilot.pause()
            app.screen.dismiss(None)
            await pilot.pause()
            assert db.list_tasks() == []
        db.close()


@pytest.mark.asyncio
async def test_submit_with_active_project_filter_skips_picker():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        proj = db.add_project("docs")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await _wait_for_dashboard(pilot, app)
            app.set_project_filter(ProjectFilter.project(proj.id))
            await pilot.pause()
            app.submit_new_task("Write release notes")
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)  # no modal
            tasks = db.list_tasks()
            assert len(tasks) == 1
            assert tasks[0].project_id == proj.id
        db.close()


@pytest.mark.asyncio
async def test_submit_with_explicit_at_project_skips_picker():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "d.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await _wait_for_dashboard(pilot, app)
            app.submit_new_task("write notes @docs")
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)
            tasks = db.list_tasks()
            assert len(tasks) == 1
            assert tasks[0].project_id is not None
            assert db.get_project(tasks[0].project_id).name == "docs"
        db.close()
