import tempfile
from pathlib import Path

import pytest

from pomban.app import PomodoroApp
from pomban.core.db import DB
from pomban.screens.dashboard import DashboardScreen
from pomban.screens.help import HelpScreen


async def _to_dashboard(pilot, app):
    for _ in range(40):
        await pilot.pause()
        if isinstance(app.screen, DashboardScreen):
            return
    raise AssertionError("dashboard never active")


@pytest.mark.asyncio
async def test_help_opens_and_renders_without_crashing():
    with tempfile.TemporaryDirectory() as td:
        app = PomodoroApp(db=DB(Path(td) / "h.db"), fast=True)
        async with app.run_test(size=(120, 40)) as pilot:
            await _to_dashboard(pilot, app)
            await pilot.press("question_mark")
            await pilot.pause()
            # Reaching here means the screen pushed and the compositor rendered it
            # without crashing — the regression was a render-time AttributeError
            # because _render() shadowed Textual's internal Widget._render().
            assert isinstance(app.screen, HelpScreen)
            static = next(iter(app.screen.query("Static")))
            assert "keybindings" in str(static.render())
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)
        app.db.close()
