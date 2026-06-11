from unittest.mock import patch

from pomban.plugins import PluginRegistry, git_sync


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
    log_files = list((tmp_path / "pomban").iterdir())
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
        argv = popen.call_args[0][0]
        # Fire-and-forget single process (non-blocking on shutdown).
        assert argv[0] == "sh" and argv[1] == "-c"
        script = argv[2]
        assert "git add -A" in script and "git commit" in script
        # Injection-safe: repo path + message are positional params ($1/$2),
        # NOT interpolated into the script text.
        assert str(tmp_path) not in script
        assert str(tmp_path) in argv[3:]  # passed as a positional arg
        # Detached so a slow add can't hang the app on exit.
        assert popen.call_args.kwargs.get("start_new_session") is True


def test_git_sync_is_injection_safe(tmp_path):
    # A repo path containing shell metacharacters must not break out of the command.
    evil = tmp_path / "a; rm -rf ~"
    evil.mkdir()
    (evil / ".git").mkdir()
    with patch("subprocess.Popen") as popen:
        git_sync(evil)
        argv = popen.call_args[0][0]
        # The dangerous path appears only as data (a positional arg), never in the script.
        assert str(evil) not in argv[2]
        assert str(evil) in argv[3:]
