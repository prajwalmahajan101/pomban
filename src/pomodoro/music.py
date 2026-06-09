"""Drive an external music player (default: cliamp) from focus/break phase events.

Fire-and-forget, error-isolated — mirrors notifications.run_hook: a missing player
binary logs one line and returns silently rather than crashing the TUI.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from pomodoro.core.config import MusicSection

# Maps a phase event to the configured subcommand attribute on MusicSection.
_EVENT_ATTR = {
    "focus_start": "on_focus_start",
    "focus_end": "on_focus_end",
    "break_start": "on_break_start",
    "break_end": "on_break_end",
}


class MusicController:
    def __init__(self, cfg: MusicSection) -> None:
        self.cfg = cfg
        self._daemon_proc = None  # the headless instance we spawned (if any)
        self._stopping = False  # set on shutdown to win the start/stop race

    # ---- headless daemon lifecycle ----
    def start_daemon(self):
        """Start a headless player instance in the background so the control panel
        works without a separately-launched player.

        Idempotent and best-effort: no-ops if music is disabled, autostart is off,
        the binary is missing, daemon args are empty, or an instance is already
        running. Returns the spawned Popen, or None.
        """
        if not self.cfg.enabled or not self.cfg.autostart:
            return None
        args = (self.cfg.daemon_args or "").split()
        if not args:
            return None  # this player has no headless mode configured
        player = self.cfg.player
        if shutil.which(player) is None:
            self._log(f"player {player!r} not found; cannot start daemon")
            return None
        if self.is_running():
            return None  # something is already serving IPC — don't double-start
        if self._stopping:
            return None  # app is already shutting down — don't spawn an orphan
        try:
            proc = subprocess.Popen(
                [player, *args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except (OSError, ValueError) as e:
            self._log(f"failed to start daemon: {e}")
            return None
        self._daemon_proc = proc
        # stop_daemon() may have run on the main thread while this worker thread was
        # spawning; if so, terminate what we just started so it doesn't leak.
        if self._stopping:
            self._terminate(proc)
            self._daemon_proc = None
            return None
        return proc

    def stop_daemon(self) -> None:
        """Terminate the daemon we started (only ours — never a pre-existing one)."""
        self._stopping = True
        self._terminate(self._daemon_proc)
        self._daemon_proc = None

    @staticmethod
    def _terminate(proc) -> None:
        if proc is not None and proc.poll() is None:
            with contextlib.suppress(Exception):
                proc.terminate()

    def fire(self, event: str) -> None:
        """Run the subcommand configured for a phase event (e.g. 'focus_start')."""
        attr = _EVENT_ATTR.get(event)
        if attr is None:
            return
        subcmd = getattr(self.cfg, attr, "")
        if subcmd:
            self._run(subcmd)

    def toggle(self) -> None:
        self._run("toggle")

    def next(self) -> None:
        self._run("next")

    def prev(self) -> None:
        self._run("prev")

    def volume(self, db_delta: float) -> None:
        """Adjust volume by a signed dB delta (cliamp `volume <dB>`)."""
        self._run("volume", f"{db_delta:+g}")

    def seek(self, seconds: float, *, relative: bool = False, current: float | None = None) -> None:
        """Seek playback. cliamp `seek <seconds>` is an *absolute* position, so a
        relative skip is computed from ``current`` (the polled position). Clamped
        at 0; the seconds are rounded to a whole number for the CLI."""
        base = (current or 0.0) if relative else 0.0
        target = max(0, round(base + seconds))
        self._run("seek", str(target))

    def stop(self) -> None:
        self._run("stop")

    def shuffle(self, mode: str = "toggle") -> None:
        """cliamp `shuffle [on|off|toggle]`."""
        self._run("shuffle", mode)

    def repeat(self, mode: str = "cycle") -> None:
        """cliamp `repeat [off|all|one|cycle]`."""
        self._run("repeat", mode)

    def speed(self, ratio: float) -> None:
        """cliamp `speed <ratio>` (clamped to the supported 0.25–2.0 range)."""
        self._run("speed", f"{max(0.25, min(2.0, float(ratio))):g}")

    def load_playlist(self, name: str, *, autoplay: bool = True) -> None:
        """cliamp `load <name>` — load a saved playlist; start playback by default.

        Plain `load` only loads (the player stays stopped); `--auto-play` is what
        actually starts playback when you pick a playlist."""
        if not name:
            return
        if autoplay:
            self._run("load", name, "--auto-play")
        else:
            self._run("load", name)

    def play(self) -> None:
        """Resume playback (cliamp `play`)."""
        self._run("play")

    def play_track(self, path: str) -> None:
        """Queue a specific file and start it (cliamp `queue <path> --auto-play`)."""
        if path:
            self._run("queue", path, "--auto-play")

    # ---- read-only status (for the in-app control panel) ----
    def status(self) -> dict | None:
        """Return the player's now-playing state as a dict, or None.

        None means: music disabled, player binary missing, player not running
        (no socket), timed out, or non-JSON output. Cheap, read-only, isolated —
        safe to poll. Assumes a ``status --json`` subcommand (cliamp); other
        players simply return None and the panel degrades.
        """
        player = self.cfg.player
        if shutil.which(player) is None:
            return None
        try:
            proc = subprocess.run(
                [player, "status", "--json"],
                capture_output=True,
                text=True,
                timeout=0.5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        out = (proc.stdout or "").strip()
        if not out or not out.startswith(("{", "[")):
            return None  # e.g. "cliamp is not running (no socket ...)"
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def is_running(self) -> bool:
        return self.status() is not None

    def visstream_popen(self, fps: int = 20):
        """Spawn `<player> visstream --fps N`, returning a Popen with a line-buffered
        stdout pipe (NDJSON, one frame per line), or None if unavailable."""
        player = self.cfg.player
        if not self.cfg.enabled or shutil.which(player) is None:
            return None
        try:
            return subprocess.Popen(
                [player, "visstream", "--fps", str(int(fps))],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except (OSError, ValueError) as e:
            self._log(f"failed to start visstream: {e}")
            return None

    def _run_read(self, *args: str, timeout: float = 0.7) -> str | None:
        """Run a read-only subcommand and return stdout, or None on any failure.

        Mirrors status(): disabled/which guard, short timeout, never raises — for
        commands that report state (history, playlist list). Safe to poll off-thread.
        """
        if not self.cfg.enabled:
            return None
        player = self.cfg.player
        if shutil.which(player) is None:
            return None
        try:
            proc = subprocess.run([player, *args], capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            return None
        return proc.stdout or ""

    def history(self, limit: int = 20) -> list[dict] | None:
        """Recently-played tracks via `history --limit N --json`, or None."""
        out = self._run_read("history", "--limit", str(int(limit)), "--json")
        if out is None:
            return None
        out = out.strip()
        if not out or not out.startswith(("[", "{")):
            return None
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict):
            data = data.get("entries") or data.get("history") or data.get("items") or []
        return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else None

    def playlists(self) -> list[str] | None:
        """Saved playlist names via `playlist list` (tolerant text parse), or None."""
        out = self._run_read("playlist", "list")
        if out is None:
            return None
        from pomodoro.music_view import parse_playlists

        return parse_playlists(out)

    def playlist_tracks(self, name: str) -> list[dict] | None:
        """Tracks in a saved playlist via `playlist show <name> --json`, or None.

        Returns a list of ``{"path","title","artist"}`` dicts (cliamp's JSON shape)."""
        if not name:
            return None
        out = self._run_read("playlist", "show", name, "--json")
        if out is None:
            return None
        out = out.strip()
        if not out or not out.startswith(("[", "{")):
            return None
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return None
        return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else None

    def _run(self, subcmd: str, *args: str) -> None:
        if not self.cfg.enabled:
            return
        player = self.cfg.player
        if shutil.which(player) is None:
            self._log(f"player {player!r} not found on PATH; skipped {subcmd!r}")
            return
        try:
            subprocess.Popen(
                [player, subcmd, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except (FileNotFoundError, OSError) as e:
            self._log(f"failed to run {player} {subcmd}: {e}")

    @staticmethod
    def _log(message: str) -> None:
        log_dir = (
            Path(os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state"))
            / "pomodoro"
        )
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "music.log", "a") as f:
                f.write(message + "\n")
        except OSError:
            pass
