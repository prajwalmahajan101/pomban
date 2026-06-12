"""Test for the M4 by-tag panel on StatsScreen."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.stats import StatsScreen


async def wait_for(pilot, screen_cls, *, tries: int = 40):
    for _ in range(tries):
        await pilot.pause()
        if isinstance(pilot.app.screen, screen_cls):
            return pilot.app.screen
    raise AssertionError(
        f"Screen {screen_cls.__name__} never became active: {type(pilot.app.screen)}"
    )


def _seed_tagged_sessions(db: DB) -> None:
    t1 = db.add_task("Slides", tags="deep,writing")
    t2 = db.add_task("Standup", tags="meeting")
    sid1 = db.start_session("focus", planned_seconds=1500, task_ids=[t1.id])
    db.end_session(sid1, actual_seconds=1500, completed=True)
    sid2 = db.start_session("focus", planned_seconds=600, task_ids=[t2.id])
    db.end_session(sid2, actual_seconds=600, completed=True)


@pytest.mark.asyncio
async def test_stats_renders_by_tag_block_with_tags():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "st.db")
        _seed_tagged_sessions(db)
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("3")
            screen = await wait_for(pilot, StatsScreen)
            from pomban.widgets.bar_chart import BarChart

            chart = screen.query_one("#by-tag", BarChart)
            text = str(chart.render())
            assert "deep" in text
            assert "meeting" in text
        db.close()


@pytest.mark.asyncio
async def test_stats_by_tag_empty_state():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "ste.db")
        app = PomodoroApp(db=db, fast=True)
        async with app.run_test() as pilot:
            await wait_for(pilot, DashboardScreen)
            await pilot.press("3")
            screen = await wait_for(pilot, StatsScreen)
            from pomban.widgets.bar_chart import BarChart

            chart = screen.query_one("#by-tag", BarChart)
            assert "No tagged focus sessions" in str(chart.render())
        db.close()
