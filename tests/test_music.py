from unittest.mock import patch

from pomodoro.core.config import MusicSection
from pomodoro.music import MusicController


def test_disabled_is_a_noop():
    mc = MusicController(MusicSection(enabled=False))
    with patch("pomodoro.music.subprocess.Popen") as popen:
        mc.fire("focus_start")
        mc.toggle()
        mc.next()
        assert not popen.called


def test_focus_start_plays():
    mc = MusicController(MusicSection(enabled=True, player="cliamp"))
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.fire("focus_start")
        assert popen.called
        assert popen.call_args[0][0] == ["cliamp", "play"]


def test_missing_binary_logs_and_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    mc = MusicController(MusicSection(enabled=True, player="definitely-not-installed"))
    with (
        patch("pomodoro.music.shutil.which", return_value=None),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.fire("focus_start")  # must not raise
        assert not popen.called
    log = tmp_path / "pomodoro" / "music.log"
    assert log.exists()
    assert "not found" in log.read_text()


def test_toggle_sends_toggle_subcommand():
    mc = MusicController(MusicSection(enabled=True, player="cliamp"))
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.toggle()
        assert popen.call_args[0][0] == ["cliamp", "toggle"]


def test_empty_subcommand_event_is_skipped():
    # on_break_start defaults to "" — firing it should do nothing.
    mc = MusicController(MusicSection(enabled=True, player="cliamp", on_break_start=""))
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.fire("break_start")
        assert not popen.called


def test_prev_sends_prev_subcommand():
    mc = MusicController(MusicSection(enabled=True, player="cliamp"))
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.prev()
        assert popen.call_args[0][0] == ["cliamp", "prev"]


def test_volume_passes_signed_db():
    mc = MusicController(MusicSection(enabled=True, player="cliamp"))
    with (
        patch("pomodoro.music.shutil.which", return_value="/usr/bin/cliamp"),
        patch("pomodoro.music.subprocess.Popen") as popen,
    ):
        mc.volume(2.0)
        assert popen.call_args[0][0] == ["cliamp", "volume", "+2"]
        mc.volume(-3.5)
        assert popen.call_args[0][0] == ["cliamp", "volume", "-3.5"]


def test_status_parses_json(monkeypatch):
    import subprocess

    mc = MusicController(MusicSection(enabled=True, player="cliamp"))
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/cliamp")
    cp = subprocess.CompletedProcess([], 0, stdout='{"title":"Song","playing":true}', stderr="")
    monkeypatch.setattr("pomodoro.music.subprocess.run", lambda *a, **k: cp)
    data = mc.status()
    assert data == {"title": "Song", "playing": True}
    assert mc.is_running() is True


def test_status_none_when_not_running(monkeypatch):
    import subprocess

    mc = MusicController(MusicSection(enabled=True, player="cliamp"))
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/cliamp")
    cp = subprocess.CompletedProcess([], 0, stdout="cliamp is not running (no socket)", stderr="")
    monkeypatch.setattr("pomodoro.music.subprocess.run", lambda *a, **k: cp)
    assert mc.status() is None
    assert mc.is_running() is False


def test_status_none_when_binary_missing(monkeypatch):
    mc = MusicController(MusicSection(enabled=True, player="nope"))
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: None)
    assert mc.status() is None


def test_panel_extract_fields():
    from pomodoro.widgets.music_panel import _extract

    out = _extract({"track": {"title": "T", "artist": "A"}, "state": "playing", "volume": -3})
    assert out["title"] == "T" and out["artist"] == "A"
    assert out["playing"] is True and out["volume"] == -3


def test_panel_parse_frame():
    from pomodoro.widgets.music_panel import MusicPanel

    assert MusicPanel._parse_frame("[1, 2, 3]") == [1.0, 2.0, 3.0]
    assert MusicPanel._parse_frame('{"bands":[0.5,0.25]}') == [0.5, 0.25]
    assert MusicPanel._parse_frame("not json") is None
    assert MusicPanel._parse_frame("") is None


def test_start_daemon_spawns_when_enabled_and_not_running(monkeypatch):
    mc = MusicController(MusicSection(enabled=True, player="cliamp"))
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/cliamp")
    monkeypatch.setattr(mc, "is_running", lambda: False)
    with patch("pomodoro.music.subprocess.Popen") as popen:
        mc.start_daemon()
        assert popen.called
        assert popen.call_args[0][0] == ["cliamp", "--daemon"]


def test_start_daemon_noop_when_already_running(monkeypatch):
    mc = MusicController(MusicSection(enabled=True, player="cliamp"))
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/cliamp")
    monkeypatch.setattr(mc, "is_running", lambda: True)
    with patch("pomodoro.music.subprocess.Popen") as popen:
        assert mc.start_daemon() is None
        assert not popen.called


def test_start_daemon_noop_when_disabled():
    mc = MusicController(MusicSection(enabled=False, player="cliamp"))
    with patch("pomodoro.music.subprocess.Popen") as popen:
        assert mc.start_daemon() is None
        assert not popen.called


def test_start_daemon_noop_when_no_daemon_args(monkeypatch):
    mc = MusicController(MusicSection(enabled=True, player="mpv", daemon_args=""))
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/mpv")
    with patch("pomodoro.music.subprocess.Popen") as popen:
        assert mc.start_daemon() is None
        assert not popen.called


def test_stop_daemon_only_kills_our_process():
    mc = MusicController(MusicSection(enabled=True, player="cliamp"))
    # No daemon started → stop is a harmless no-op.
    mc.stop_daemon()

    # Simulate a running daemon we own.
    class FakeProc:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    proc = FakeProc()
    mc._daemon_proc = proc
    mc.stop_daemon()
    assert proc.terminated is True
    assert mc._daemon_proc is None


def test_start_daemon_skips_when_stopping(monkeypatch):
    # Race fix: if stop_daemon() already ran (shutdown), start_daemon must not spawn.
    mc = MusicController(MusicSection(enabled=True, player="cliamp"))
    monkeypatch.setattr("pomodoro.music.shutil.which", lambda p: "/usr/bin/cliamp")
    monkeypatch.setattr(mc, "is_running", lambda: False)
    mc.stop_daemon()  # sets _stopping
    with patch("pomodoro.music.subprocess.Popen") as popen:
        assert mc.start_daemon() is None
        assert not popen.called


def test_stop_daemon_sets_stopping_flag():
    mc = MusicController(MusicSection(enabled=True, player="cliamp"))
    assert mc._stopping is False
    mc.stop_daemon()
    assert mc._stopping is True
