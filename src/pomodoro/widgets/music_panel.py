"""In-app music control panel.

Renders now-playing state read from ``cliamp status --json`` and drives playback
through the control CLI (toggle / next / prev / volume). It does **not** embed
cliamp's own TUI — it's a native Textual widget. Optionally streams
``cliamp visstream`` (NDJSON) into a sparkline visualizer.

All player I/O is off the UI thread: status reads run via ``asyncio.to_thread``
and the visualizer reads its pipe in a thread worker, so a slow or missing
player never blocks the timer.
"""

from __future__ import annotations

import contextlib
import json

from rich.markup import escape
from textual import work
from textual.containers import Vertical
from textual.widgets import Static
from textual.worker import get_current_worker

from pomodoro.core.colors import adapt
from pomodoro.music_view import extract as _extract
from pomodoro.widgets.sparkline import Sparkline


class MusicPanel(Vertical):
    can_focus = True

    DEFAULT_CSS = """
    MusicPanel {
        height: auto;
        padding: 0 1;
    }
    MusicPanel #np-title { height: auto; }
    MusicPanel #np-meta { height: auto; color: $text-muted; }
    MusicPanel #vis { height: 1; }
    MusicPanel #vis.-hidden { display: none; }
    """

    BINDINGS = [
        ("space", "toggle", "Play/Pause"),
        ("n", "next", "Next"),
        ("p", "prev", "Prev"),
        ("plus,equals_sign,equal", "vol_up", "Vol +"),
        ("minus,underscore", "vol_down", "Vol −"),
        ("V,shift+v", "toggle_visualizer", "Visualizer"),
    ]

    def __init__(
        self,
        controller,
        *,
        visualizer: bool = False,
        poll_seconds: float = 1.0,
        vis_fps: int = 20,
        volume_step: float = 2.0,
    ) -> None:
        super().__init__(id="music-pane")
        self.controller = controller
        self.visualizer = visualizer
        self.poll_seconds = max(0.25, float(poll_seconds))
        self.vis_fps = int(vis_fps)
        self.volume_step = float(volume_step)
        self._vis_proc = None

    def compose(self):
        yield Static("[b]♪ Music[/]", id="np-title")
        yield Static("", id="np-meta")
        yield Sparkline(id="vis")

    def on_mount(self) -> None:
        self.query_one("#vis").set_class(not self.visualizer, "-hidden")
        self.set_interval(self.poll_seconds, self.refresh_status)
        self.refresh_status()
        if self.visualizer:
            self._run_visualizer()

    # ---- status polling (off-thread) ----
    @work(exclusive=True, group="music-status")
    async def refresh_status(self) -> None:
        import asyncio

        status = await asyncio.to_thread(self.controller.status)
        self._apply_status(status)

    def _apply_status(self, status: dict | None) -> None:
        title = self.query_one("#np-title", Static)
        meta = self.query_one("#np-meta", Static)
        if not status:
            title.update("[b]♪ Music[/]  [dim]— not running[/]")
            meta.update("[dim]start cliamp · press 7 for the full player[/]")
            return
        info = _extract(status)
        icon = "▶" if info["playing"] else "⏸"
        if info["title"]:
            # Escape player-supplied metadata so a title like "intro [/] outro"
            # can't break the Rich markup and crash the (polled) render.
            title.update(f"[b]{icon} {escape(str(info['title']))}[/]")
        else:
            # Daemon up but nothing loaded (e.g. state="stopped") — show the state.
            label = escape(str(info["state"] or ("playing" if info["playing"] else "idle")))
            title.update(f"[b]♪ {label}[/]  [dim](queue a track in cliamp)[/]")
        bits = []
        if info["artist"]:
            bits.append(escape(str(info["artist"])))
        if info["volume"] is not None:
            bits.append(f"vol {escape(str(info['volume']))}")
        meta.update("[dim]" + "  ·  ".join(bits) + "[/]" if bits else "")

    # ---- visualizer (NDJSON pipe in a thread worker) ----
    @work(thread=True, exclusive=True, group="music-vis")
    def _run_visualizer(self) -> None:
        proc = self.controller.visstream_popen(self.vis_fps)
        if proc is None or proc.stdout is None:
            return
        self._vis_proc = proc
        worker = get_current_worker()
        try:
            for line in proc.stdout:
                if worker.is_cancelled:
                    break
                frame = self._parse_frame(line)
                if frame:
                    self.app.call_from_thread(self._apply_frame, frame)
        finally:
            with contextlib.suppress(Exception):
                proc.terminate()
            self._vis_proc = None

    @staticmethod
    def _parse_frame(line: str) -> list[float] | None:
        line = line.strip()
        if not line:
            return None
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        if isinstance(data, list):
            values = data
        elif isinstance(data, dict):
            values = data.get("bands") or data.get("values") or data.get("magnitudes")
        else:
            return None
        if not isinstance(values, list):
            return None
        try:
            return [float(v) for v in values]
        except (TypeError, ValueError):
            return None

    def _apply_frame(self, frame: list[float]) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#vis", Sparkline).set_values(
                frame, color=adapt("bright_cyan") or "cyan"
            )

    # ---- actions ----
    def action_toggle(self) -> None:
        self.controller.toggle()
        self.refresh_status()

    def action_next(self) -> None:
        self.controller.next()
        self.refresh_status()

    def action_prev(self) -> None:
        self.controller.prev()
        self.refresh_status()

    def action_vol_up(self) -> None:
        self.controller.volume(self.volume_step)
        self.refresh_status()

    def action_vol_down(self) -> None:
        self.controller.volume(-self.volume_step)
        self.refresh_status()

    def action_toggle_visualizer(self) -> None:
        self.visualizer = not self.visualizer
        self.query_one("#vis").set_class(not self.visualizer, "-hidden")
        if self.visualizer:
            self._run_visualizer()
        else:
            self.workers.cancel_group(self, "music-vis")
            if self._vis_proc is not None:
                with contextlib.suppress(Exception):
                    self._vis_proc.terminate()
                self._vis_proc = None
