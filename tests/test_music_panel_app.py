import tempfile
from pathlib import Path

import pytest

from pomodoro.app import PomodoroApp
from pomodoro.core.config import Config
from pomodoro.core.db import DB
from pomodoro.screens.dashboard import DashboardScreen
from pomodoro.widgets.music_panel import MusicPanel


def _config_with_music():
    cfg = Config()
    cfg.music.enabled = True
    cfg.music.show_panel = True
    cfg.music.visualizer = False
    # A player that isn't installed → status() returns None, no subprocess spawned.
    cfg.music.player = "definitely-not-a-real-player-xyz"
    return cfg


@pytest.mark.asyncio
async def test_music_panel_mounts_and_shows_not_running():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        app = PomodoroApp(db=db, fast=True, config=_config_with_music())
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.screen.query_one(MusicPanel)
            assert panel is not None
            await pilot.pause()
            from textual.widgets import Static

            title = panel.query_one("#np-title", Static).render()
            assert "not running" in str(title)
        db.close()


@pytest.mark.asyncio
async def test_music_panel_does_not_overlap_footer():
    # Regression: the panel used to dock:bottom and collide with the Footer's row.
    from textual.widgets import Footer

    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        app = PomodoroApp(db=db, fast=True, config=_config_with_music())
        async with app.run_test(size=(206, 50)) as pilot:
            await pilot.pause()
            panel = app.screen.query_one(MusicPanel).region
            footer = app.screen.query_one(Footer).region
            main = app.screen.query_one("#main").region

            def rows(r):
                return (r.y, r.y + r.height - 1)

            def overlap(a, b):
                a, b = rows(a), rows(b)
                return not (a[1] < b[0] or b[1] < a[0])

            assert not overlap(panel, footer), "music panel overlaps footer"
            assert not overlap(panel, main), "music panel overlaps main area"
        db.close()


@pytest.mark.asyncio
async def test_music_panel_absent_when_disabled():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        app = PomodoroApp(db=db, fast=True, config=Config())  # music disabled by default
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)
            assert len(app.screen.query(MusicPanel)) == 0
        db.close()
