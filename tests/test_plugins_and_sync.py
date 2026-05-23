import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pomodoro.plugins import PluginRegistry, git_sync


class GoodPlugin:
    started: list = []
    completed: list = []

    @classmethod
    def on_phase_started(cls, phase, task):
        cls.started.append((phase, task))

    @classmethod
    def on_phase_completed(cls, phase, task, completed):
        cls.completed.append((phase, task, completed))


class BadPlugin:
    @staticmethod
    def on_phase_started(phase, task):
        raise RuntimeError("boom")


def test_plugin_registry_fires_callbacks():
    reg = PluginRegistry()
    GoodPlugin.started.clear()
    reg.register(GoodPlugin)
    reg.fire("on_phase_started", "focus", "Demo")
    assert GoodPlugin.started == [("focus", "Demo")]


def test_plugin_error_does_not_propagate(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    reg = PluginRegistry()
    reg.register(BadPlugin)
    reg.register(GoodPlugin)
    GoodPlugin.started.clear()
    # Should not raise even though BadPlugin raises.
    reg.fire("on_phase_started", "focus", "X")
    # GoodPlugin still ran:
    assert GoodPlugin.started == [("focus", "X")]
    # Error logged
    log_files = list((tmp_path / "pomodoro").iterdir())
    assert any(f.name == "plugins.log" for f in log_files)


def test_git_sync_noop_without_git_dir(tmp_path):
    # Should silently do nothing, no exception.
    git_sync(tmp_path)


def test_git_sync_calls_commit_when_repo_present(tmp_path):
    # Set up a fake git repo
    (tmp_path / ".git").mkdir()
    with patch("subprocess.Popen") as popen:
        git_sync(tmp_path)
        assert popen.called
        args = popen.call_args[0][0]
        assert "git add -A" in args[-1]
        assert "git commit" in args[-1]
