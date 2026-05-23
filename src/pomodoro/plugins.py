"""Lightweight plugin system.

Plugins are Python entry points under group `pomodoro.hooks` exposing callables:
- on_phase_started(phase: str, task_title: str | None) -> None
- on_phase_completed(phase: str, task_title: str | None, completed: bool) -> None

Every callback is wrapped in try/except so plugin errors never crash the app —
they're logged to ~/.local/state/pomodoro/plugins.log.
"""
from __future__ import annotations

import os
from importlib.metadata import entry_points
from pathlib import Path


def _log_path() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state"))
    p = base / "pomodoro"
    p.mkdir(parents=True, exist_ok=True)
    return p / "plugins.log"


def _log(msg: str) -> None:
    try:
        with open(_log_path(), "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass


class PluginRegistry:
    def __init__(self) -> None:
        self.callbacks: list[object] = []

    def discover(self) -> None:
        try:
            eps = entry_points(group="pomodoro.hooks")
        except TypeError:
            # Older importlib.metadata API
            eps = entry_points().get("pomodoro.hooks", [])
        for ep in eps:
            try:
                obj = ep.load()
                self.callbacks.append(obj)
            except Exception as e:
                _log(f"[load-error] {ep.name}: {e}")

    def register(self, callback: object) -> None:
        """Register a callback module/object directly (useful for tests + examples)."""
        self.callbacks.append(callback)

    def fire(self, hook_name: str, *args, **kwargs) -> None:
        for cb in self.callbacks:
            fn = getattr(cb, hook_name, None)
            if not callable(fn):
                continue
            try:
                fn(*args, **kwargs)
            except Exception as e:
                _log(f"[run-error] {hook_name}: {e}")


_registry = PluginRegistry()


def registry() -> PluginRegistry:
    return _registry


def git_sync(repo_dir: Path | str) -> None:
    """Run `git add -A && git commit -m '...'` in repo_dir. Non-blocking. Silent on failure."""
    import shutil
    import subprocess
    from datetime import datetime

    if not shutil.which("git"):
        return
    repo = Path(repo_dir)
    if not (repo / ".git").exists():
        return
    msg = f"pomodoro sync {datetime.now().isoformat(timespec='seconds')}"
    try:
        subprocess.Popen(
            ["sh", "-c", f"cd {repo} && git add -A && git commit -m '{msg}' >/dev/null 2>&1"],
        )
    except Exception as e:
        _log(f"[git-sync-error] {e}")
