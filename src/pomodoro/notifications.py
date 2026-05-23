"""End-of-phase notifications: desktop popup, terminal bell, sound. All optional."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class NotifyConfig:
    desktop: bool = True
    bell: bool = True
    sound: bool = True
    sound_file: str | None = None  # default: aplay/paplay's bundled freedesktop sound


def _spawn(cmd: list[str]) -> None:
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, OSError):
        pass


def desktop(title: str, body: str) -> None:
    if shutil.which("notify-send"):
        _spawn(["notify-send", "-a", "Pomodoro", title, body])


def play_sound(path: str | None = None) -> None:
    candidates = [
        path,
        "/usr/share/sounds/freedesktop/stereo/complete.oga",
        "/usr/share/sounds/freedesktop/stereo/bell.oga",
    ]
    sound = next((p for p in candidates if p), None)
    if not sound:
        return
    for player in ("paplay", "aplay", "ffplay"):
        if shutil.which(player):
            args = [player, sound]
            if player == "ffplay":
                args = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", sound]
            _spawn(args)
            return


def run_hook(command: str | None, env_extra: dict | None = None) -> None:
    """Fire-and-forget shell hook. Never raises. Logs errors to ~/.local/state/pomodoro/hooks.log."""
    if not command:
        return
    import os
    from pathlib import Path

    log_dir = Path(os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")) / "pomodoro"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "hooks.log"
        env = {**os.environ, **(env_extra or {})}
        with open(log_path, "ab", buffering=0) as logf:
            subprocess.Popen(["sh", "-c", command], stdout=logf, stderr=logf, env=env)
    except (FileNotFoundError, OSError) as e:
        try:
            with open(log_dir / "hooks.log", "a") as logf:
                logf.write(f"[hook-error] {command}: {e}\n")
        except Exception:
            pass


def fire(title: str, body: str, cfg: NotifyConfig) -> None:
    if cfg.desktop:
        desktop(title, body)
    if cfg.sound:
        play_sound(cfg.sound_file)
    # Terminal bell + visual flash handled inside the Textual app (see app.py),
    # because they need to write to the active screen.
