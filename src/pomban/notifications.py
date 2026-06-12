"""End-of-phase notifications: desktop popup, terminal bell, sound. All optional."""

from __future__ import annotations

import contextlib
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, time


@dataclass
class NotifyConfig:
    desktop: bool = True
    bell: bool = True
    sound: bool = True
    sound_file: str | None = None  # default: aplay/paplay's bundled freedesktop sound
    # Inclusive [start, end] window — outside it desktop popups + sound are
    # suppressed (bell + visual flash still fire). ``None`` disables the gate.
    working_hours: tuple[time, time] | None = field(default=None)


def _spawn(cmd: list[str]) -> None:
    with contextlib.suppress(FileNotFoundError, OSError):
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
    """Fire-and-forget shell hook. Never raises. Logs errors to ~/.local/state/pomban/hooks.log."""
    if not command:
        return
    import os
    from pathlib import Path

    log_dir = (
        Path(os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")) / "pomban"
    )
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


def within_working_hours(cfg: NotifyConfig, now: datetime | None = None) -> bool:
    """True iff cfg has no window, or ``now`` falls inside [start, end] (inclusive)."""
    if cfg.working_hours is None:
        return True
    start, end = cfg.working_hours
    t = (now or datetime.now()).time()
    if start <= end:
        return start <= t <= end
    # Overnight window (e.g. 22:00–06:00).
    return t >= start or t <= end


def fire(title: str, body: str, cfg: NotifyConfig) -> None:
    quiet = not within_working_hours(cfg)
    if cfg.desktop and not quiet:
        desktop(title, body)
    if cfg.sound and not quiet:
        play_sound(cfg.sound_file)
    # Terminal bell + visual flash handled inside the Textual app (see app.py),
    # because they need to write to the active screen.
