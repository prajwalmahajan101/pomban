"""Pilot test for SprintCompleteModal — fires when the sprint hits target."""

from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.sprint_complete import SprintCompleteModal


async def wait_for(pilot, screen_cls, *, tries: int = 60):
    for _ in range(tries):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(
        f"Screen {screen_cls.__name__} never became active: {type(pilot.app.screen)}"
    )


@pytest.mark.asyncio
async def test_sprint_complete_modal_fires_on_target_hit():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "sc.db")
        project = db.add_project("P")
        start = date.today().isoformat()
        end = (date.today() + timedelta(days=14)).isoformat()
        sprint = db.add_sprint(project.id, "S", start, end, pomodoro_target=1)
        db.activate_sprint(sprint.id)
        task = db.add_task("T", project_id=project.id, sprint_id=sprint.id)
        db.kv_set("ui.active_project", f"project:{project.id}")
        db.kv_set("ui.active_sprint", str(sprint.id))

        app = PomodoroApp(db=db, fast=True)
        # Force auto-advance so _on_phase_completed finalizes the session
        # immediately and the sprint-complete hook fires.
        app.config.timer.auto_advance = True

        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            # Drive the engine directly: start a focus session, then short-circuit
            # to the phase-completion handler (we don't need to spin the timer
            # to actually elapse in a pilot test).
            app.start_focus_on(task)
            await pilot.pause()
            app._on_phase_completed()
            await wait_for(pilot, SprintCompleteModal)
        db.close()
