"""Tests for the extended MusicController, the music_view helpers, and MusicScreen."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pomodoro import music_view
from pomodoro.app import PomodoroApp
from pomodoro.core.config import Config, MusicSection
from pomodoro.core.db import DB
from pomodoro.music import MusicController
from pomodoro.screens.dashboard import DashboardScreen


def _enabled(**kw):
    return MusicController(MusicSection(enabled=True, player="cliamp", **kw))


def _argv(popen):
    return popen.call_args[0][0]


# ---------------- controller: transport ----------------


def test_seek_absolute_rounds():
    mc = _enabled()
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.seek(7.6)
        assert _argv(popen) == ["cliamp", "seek", "8"]


def test_seek_relative_from_current():
    mc = _enabled()
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.seek(5, relative=True, current=10)
        assert _argv(popen) == ["cliamp", "seek", "15"]


def test_seek_clamps_to_zero():
    mc = _enabled()
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.seek(-100, relative=True, current=10)
        assert _argv(popen) == ["cliamp", "seek", "0"]


def test_shuffle_repeat_stop_argv():
    mc = _enabled()
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.shuffle("toggle")
        assert _argv(popen) == ["cliamp", "shuffle", "toggle"]
        mc.repeat("cycle")
        assert _argv(popen) == ["cliamp", "repeat", "cycle"]
        mc.stop()
        assert _argv(popen) == ["cliamp", "stop"]


def test_speed_clamped():
    mc = _enabled()
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.speed(1.5)
        assert _argv(popen) == ["cliamp", "speed", "1.5"]
        mc.speed(9.0)
        assert _argv(popen) == ["cliamp", "speed", "2"]
        mc.speed(0.01)
        assert _argv(popen) == ["cliamp", "speed", "0.25"]


def test_load_playlist_argv_and_empty_noop():
    mc = _enabled()
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.load_playlist("My Mix")
        assert _argv(popen) == ["cliamp", "load", "My Mix", "--auto-play"]
        popen.reset_mock()
        mc.load_playlist("")
        assert not popen.called


def test_transport_disabled_is_noop():
    mc = MusicController(MusicSection(enabled=False, player="cliamp"))
    with patch("pomodoro.music.subprocess.Popen") as popen:
        mc.seek(5)
        mc.shuffle()
        mc.repeat()
        mc.stop()
        mc.speed(1.2)
        mc.load_playlist("x")
        assert not popen.called


# ---------------- controller: read helpers ----------------


def test_history_parses_json(monkeypatch):
    mc = _enabled()
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/cliamp")
    cp = subprocess.CompletedProcess([], 0, stdout='[{"title":"A","artist":"B"}]', stderr="")
    monkeypatch.setattr("pomodoro.music.subprocess.run", lambda *a, **k: cp)
    assert mc.history() == [{"title": "A", "artist": "B"}]


def test_history_unwraps_dict(monkeypatch):
    mc = _enabled()
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/cliamp")
    cp = subprocess.CompletedProcess([], 0, stdout='{"entries":[{"title":"A"}]}', stderr="")
    monkeypatch.setattr("pomodoro.music.subprocess.run", lambda *a, **k: cp)
    assert mc.history() == [{"title": "A"}]


def test_history_none_when_not_running(monkeypatch):
    mc = _enabled()
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/cliamp")
    cp = subprocess.CompletedProcess([], 0, stdout="cliamp is not running", stderr="")
    monkeypatch.setattr("pomodoro.music.subprocess.run", lambda *a, **k: cp)
    assert mc.history() is None


def test_history_none_on_timeout(monkeypatch):
    mc = _enabled()
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/cliamp")

    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="cliamp", timeout=0.7)

    monkeypatch.setattr("pomodoro.music.subprocess.run", boom)
    assert mc.history() is None  # must not raise


def test_read_helpers_none_when_disabled():
    mc = MusicController(MusicSection(enabled=False, player="cliamp"))
    assert mc.history() is None
    assert mc.playlists() is None


def test_playlists_parses_text(monkeypatch):
    mc = _enabled()
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/cliamp")
    cp = subprocess.CompletedProcess(
        [], 0, stdout="• My Mix (12 tracks)\nChill\n1. Focus\n", stderr=""
    )
    monkeypatch.setattr("pomodoro.music.subprocess.run", lambda *a, **k: cp)
    assert mc.playlists() == ["My Mix", "Chill", "Focus"]


# ---------------- music_view helpers ----------------


def test_extract_nested_and_flags():
    out = music_view.extract(
        {
            "track": {"title": "T", "artist": "A", "duration": 100, "position": 25},
            "state": "playing",
            "volume": -3,
            "shuffle": True,
            "repeat": "All",
        }
    )
    assert out["title"] == "T" and out["artist"] == "A"
    assert out["playing"] is True and out["volume"] == -3
    assert out["position"] == 25.0 and out["duration"] == 100.0
    assert out["shuffle"] is True and out["repeat"] == "all"


def test_fmt_mmss():
    assert music_view.fmt_mmss(None) == "--:--"
    assert music_view.fmt_mmss(65) == "1:05"
    assert music_view.fmt_mmss(3725) == "1:02:05"
    assert music_view.fmt_mmss("nope") == "--:--"


def test_progress_bar_placeholder_and_filled():
    assert "--:--" in music_view.render_progress_bar(None, None)
    bar = music_view.render_progress_bar(30, 120, width=10)
    assert "0:30" in bar and "2:00" in bar


def test_now_playing_lines_escapes_hostile_metadata():
    from rich.markup import render

    line1, meta = music_view.now_playing_lines(
        music_view.extract({"title": "intro [/] outro", "artist": "a[b]c"})
    )
    render(line1)  # raises if markup is broken
    render(f"[dim]{meta}[/]")


def test_parse_playlists_tolerant():
    assert music_view.parse_playlists("") == []
    assert music_view.parse_playlists("No playlists found") == []
    assert music_view.parse_playlists("- A\n* B (3 tracks)\n") == ["A", "B"]


def test_parse_playlists_strips_cliamp_column_track_count():
    # cliamp's real `playlist list` output is column-aligned: "Name      N tracks".
    out = (
        "  Recently Played  9 tracks\n"
        "  Liked Songs      210 tracks\n"
        "  Violin           14 tracks\n"
    )
    assert music_view.parse_playlists(out) == ["Recently Played", "Liked Songs", "Violin"]


# ---------------- MusicScreen (app-level) ----------------


def _cfg(enabled=True, music_screen=True):
    cfg = Config()
    cfg.music.enabled = enabled
    cfg.music.music_screen = music_screen
    cfg.music.player = "definitely-not-a-real-player-xyz"  # status() -> None
    return cfg


@pytest.mark.asyncio
async def test_music_screen_switch_and_not_running():
    from pomodoro.screens.music import MusicScreen

    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        app = PomodoroApp(db=db, fast=True, config=_cfg(enabled=True))
        async with app.run_test() as pilot:
            await pilot.press("7")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, MusicScreen)
            from textual.widgets import Static

            now = app.screen.query_one("#np-now", Static)
            assert "not running" in str(now.render())
        db.close()


@pytest.mark.asyncio
async def test_music_screen_shows_disabled_message():
    from pomodoro.screens.music import MusicScreen

    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        app = PomodoroApp(db=db, fast=True, config=_cfg(enabled=False, music_screen=True))
        async with app.run_test() as pilot:
            await pilot.press("7")
            await pilot.pause()
            assert isinstance(app.screen, MusicScreen)
            from textual.widgets import Static

            now = app.screen.query_one("#np-now", Static)
            assert "disabled" in str(now.render()).lower()
        db.close()


@pytest.mark.asyncio
async def test_music_screen_absent_when_disabled_config():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        app = PomodoroApp(db=db, fast=True, config=_cfg(enabled=True, music_screen=False))
        async with app.run_test() as pilot:
            await pilot.press("7")
            await pilot.pause()
            # music_screen disabled -> not installed -> 7 is a no-op, stay on dashboard
            assert isinstance(app.screen, DashboardScreen)
        db.close()


# ---------------- play flow: load (auto-play) + per-track ----------------


def test_load_playlist_autoplays_by_default():
    mc = _enabled()
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.load_playlist("My Mix")
        assert _argv(popen) == ["cliamp", "load", "My Mix", "--auto-play"]
        popen.reset_mock()
        mc.load_playlist("My Mix", autoplay=False)
        assert _argv(popen) == ["cliamp", "load", "My Mix"]
        popen.reset_mock()
        mc.load_playlist("")
        assert not popen.called


def test_play_track_queues_with_autoplay():
    mc = _enabled()
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.play_track("/music/song.mp3")
        assert _argv(popen) == ["cliamp", "queue", "/music/song.mp3", "--auto-play"]
        popen.reset_mock()
        mc.play_track("")
        assert not popen.called


def test_playlist_tracks_parses_json(monkeypatch):
    mc = _enabled()
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/cliamp")
    cp = subprocess.CompletedProcess(
        [], 0, stdout='[{"path":"/a.mp3","title":"A","artist":"X"}]', stderr=""
    )
    monkeypatch.setattr("pomodoro.music.subprocess.run", lambda *a, **k: cp)
    assert mc.playlist_tracks("Violin") == [{"path": "/a.mp3", "title": "A", "artist": "X"}]


def test_playlist_tracks_none_when_disabled():
    mc = MusicController(MusicSection(enabled=False, player="cliamp"))
    assert mc.playlist_tracks("X") is None


@pytest.mark.asyncio
async def test_music_screen_enter_plays_playlist_and_track(monkeypatch):
    from textual.widgets import ListView

    from pomodoro.screens.music import MusicScreen, _PlaylistItem, _TrackItem

    calls = {}
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        app = PomodoroApp(db=db, fast=True, config=_cfg(enabled=True))
        async with app.run_test() as pilot:
            await pilot.press("7")
            await pilot.pause()
            scr = app.screen
            assert isinstance(scr, MusicScreen)
            monkeypatch.setattr(
                scr.controller, "load_playlist", lambda name, **k: calls.__setitem__("load", name)
            )
            monkeypatch.setattr(
                scr.controller, "play_track", lambda path: calls.__setitem__("track", path)
            )
            monkeypatch.setattr(scr, "refresh_now_playing", lambda: None)
            pl = scr.query_one("#pl-list", ListView)
            pl.append(_PlaylistItem("My Mix"))
            await pilot.pause()
            scr.on_list_view_selected(ListView.Selected(pl, pl.children[-1], 0))
            assert calls.get("load") == "My Mix"
            tr = scr.query_one("#track-list", ListView)
            item = _TrackItem("/songs/a.mp3", "A")
            tr.append(item)
            await pilot.pause()
            scr.on_list_view_selected(ListView.Selected(tr, item, 0))
            assert calls.get("track") == "/songs/a.mp3"
        db.close()


# ---------------- responsive breakpoints ----------------


@pytest.mark.asyncio
async def test_narrow_terminal_gets_narrow_class():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test(size=(60, 40)) as pilot:
            await pilot.pause()
            assert app.screen.has_class("-narrow")
            assert not app.screen.has_class("-wide")
        db.close()


@pytest.mark.asyncio
async def test_wide_terminal_gets_wide_class():
    with tempfile.TemporaryDirectory() as td:
        db = DB(Path(td) / "m.db")
        app = PomodoroApp(db=db, fast=True, config=Config())
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause()
            assert app.screen.has_class("-wide")
            assert not app.screen.has_class("-narrow")
        db.close()
