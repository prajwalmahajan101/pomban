"""Full-screen music section, powered by the external cliamp player.

A richer view than the compact dashboard ``MusicPanel``: now-playing with a
progress/seek bar and shuffle/repeat/volume flags, a saved-playlist browser
(Enter plays the playlist), and a per-playlist track list (Enter queues & plays a
song). Every bit of player I/O is read off
the UI thread (``asyncio.to_thread``) and every player-supplied string is escaped
before it reaches Rich markup, so a slow, missing, or hostile player never blocks
or corrupts the render. Degrades to a clear message when music is disabled or
cliamp isn't running.
"""

from __future__ import annotations

import asyncio
import contextlib

from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, ListItem, ListView, Static

from pomodoro.music_view import (
    extract,
    flags_line,
    now_playing_lines,
    render_progress_bar,
)
from pomodoro.screens.base import AppScreen
from pomodoro.widgets.panel import panel_title


class _PlaylistItem(ListItem):
    def __init__(self, name: str) -> None:
        super().__init__(Static(escape(name)))
        self.playlist_name = name


class _TrackItem(ListItem):
    def __init__(self, path: str, label: str) -> None:
        super().__init__(Static(label))
        self.track_path = path


class MusicScreen(AppScreen):
    CSS = """
    MusicScreen { layout: vertical; }
    #np-pane { border: round $primary-darken-2; height: auto; padding: 0 1; }
    #np-now { height: auto; }
    #np-progress { height: 1; color: $text-muted; }
    #np-flags { height: 1; }
    #np-hint { height: 1; color: $text-muted; }
    #browse { height: 1fr; }
    #pl-pane, #track-pane { width: 1fr; border: round $primary-darken-2; margin: 0 1; }
    /* btop-style: accent border + accent title when the pane holds focus. */
    #pl-pane:focus-within, #track-pane:focus-within { border: round $accent; }
    #pl-pane:focus-within .pane-title,
    #track-pane:focus-within .pane-title { background: $accent; color: $text; text-style: bold; }
    .pane-title { background: $panel; padding: 0 1; }
    MusicScreen ListView { height: 1fr; background: $surface; }
    /* Responsive: on a narrow terminal, stack the two browse panes vertically. */
    MusicScreen.-narrow #browse { layout: vertical; }
    MusicScreen.-narrow #pl-pane, MusicScreen.-narrow #track-pane { width: 1fr; height: 1fr; }
    """

    BINDINGS = [
        Binding("space", "toggle", "Play/Pause"),
        Binding("n", "next", "Next"),
        Binding("p", "prev", "Prev"),
        Binding("left_square_bracket,left", "seek_back", "Seek −"),
        Binding("right_square_bracket,right", "seek_fwd", "Seek +"),
        Binding("plus,equals_sign,equal", "vol_up", "Vol +"),
        Binding("minus,underscore", "vol_down", "Vol −"),
        Binding("z", "shuffle", "Shuffle"),
        Binding("x", "repeat", "Repeat"),
        Binding("r", "refresh_all", "Refresh", show=False),
        # btop-style pane selection.
        Binding("l", "focus_pane('pl-list')", "Playlists", show=False),
        Binding("k", "focus_pane('track-list')", "Tracks", show=False),
        Binding("1", "app.switch('dashboard')", "Dashboard"),
        Binding("2", "app.switch('kanban')", "Kanban"),
        Binding("3", "app.switch('stats')", "Stats", show=False),
        Binding("4", "app.switch('history')", "History", show=False),
        Binding("5", "app.switch('projects')", "Projects", show=False),
        Binding("6", "app.switch('sprints')", "Sprints", show=False),
        Binding("7", "app.switch('music')", "Music"),
        Binding("question_mark", "app.help", "Help"),
        Binding("t", "app.cycle_theme", "Theme"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self._pos: float | None = None  # last polled position, for relative seek

    @property
    def _cfg(self):
        return self.controller.cfg

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="np-pane"):
            yield Static("[b]♪ Now Playing[/]", classes="pane-title", id="np-title")
            yield Static("", id="np-now")
            yield Static("", id="np-progress")
            yield Static("", id="np-flags")
            yield Static(
                "[dim]↵ playlist = play · ↵ track = queue & play · space = pause[/]", id="np-hint"
            )
        with Horizontal(id="browse"):
            with Vertical(id="pl-pane"):
                yield Static(panel_title("Playlists", "l"), classes="pane-title")
                yield ListView(id="pl-list")
            with Vertical(id="track-pane"):
                yield Static(panel_title("Tracks", "k"), classes="pane-title")
                yield ListView(id="track-list")
        yield Footer()

    def on_mount(self) -> None:
        if not self._cfg.enabled:
            self._render_disabled()
            return
        self.set_interval(max(0.25, float(self._cfg.poll_seconds)), self.refresh_now_playing)
        self.refresh_now_playing()
        self.refresh_playlists()

    def refresh_view(self) -> None:
        if not self._cfg.enabled:
            self._render_disabled()
            return
        self.refresh_now_playing()
        self.refresh_playlists()

    # ---- now-playing (off-thread poll) ----
    @work(exclusive=True, group="music-status")
    async def refresh_now_playing(self) -> None:
        # Skip work when this screen isn't the one on top (the interval keeps
        # firing in the background otherwise — don't spawn a cliamp subprocess
        # every second while the user is on another screen).
        if self.app.screen is not self:
            return
        status = await asyncio.to_thread(self.controller.status)
        self._apply_status(status)

    def _apply_status(self, status: dict | None) -> None:
        now = self.query_one("#np-now", Static)
        prog = self.query_one("#np-progress", Static)
        flags = self.query_one("#np-flags", Static)
        if not status:
            now.update("[b]♪ Music[/]  [dim]— cliamp not running[/]")
            prog.update("[dim]start cliamp (it's installed) and queue a track[/]")
            flags.update("")
            self._pos = None
            return
        info = extract(status)
        self._pos = info["position"]
        line1, meta = now_playing_lines(info)
        now.update(line1 + (f"\n[dim]{meta}[/]" if meta else ""))
        try:
            width = max(10, min(60, self.size.width - 16))
        except Exception:
            width = 30
        prog.update(
            render_progress_bar(
                info["position"], info["duration"], width=width, color="bright_cyan"
            )
        )
        flags.update(f"[dim]{flags_line(info)}[/]")

    def _render_disabled(self) -> None:
        self.query_one("#np-now", Static).update(
            "[b]Music is disabled[/]\n[dim]set [music].enabled = true in the config (cliamp detected ✓)[/]"
        )
        self.query_one("#np-progress", Static).update("")
        self.query_one("#np-flags", Static).update("")

    # ---- playlist + history browsers (off-thread) ----
    @work(exclusive=True, group="music-playlists")
    async def refresh_playlists(self) -> None:
        names = await asyncio.to_thread(self.controller.playlists)
        lv = self.query_one("#pl-list", ListView)
        lv.clear()
        if not names:
            self.query_one("#track-list", ListView).clear()
            return
        for name in names:
            lv.append(_PlaylistItem(name))
        # Show the first playlist's tracks so the Tracks pane isn't empty on open.
        self.refresh_tracks(names[0])

    @work(exclusive=True, group="music-tracks")
    async def refresh_tracks(self, name: str) -> None:
        tracks = await asyncio.to_thread(self.controller.playlist_tracks, name)
        lv = self.query_one("#track-list", ListView)
        lv.clear()
        if not tracks:
            return
        for t in tracks:
            title = t.get("title") or t.get("path") or "?"
            artist = t.get("artist") or t.get("uploader") or ""
            path = t.get("path") or ""
            label = escape(str(title))
            if artist:
                label += f"  [dim]{escape(str(artist))}[/]"
            lv.append(_TrackItem(path, label))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        # Arrowing through playlists updates the Tracks pane to that playlist's songs.
        if getattr(event.list_view, "id", None) != "pl-list":
            return
        name = getattr(event.item, "playlist_name", None)
        if name:
            self.refresh_tracks(name)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv_id = getattr(event.list_view, "id", None)
        if lv_id == "pl-list":
            name = getattr(event.item, "playlist_name", None)
            if not name:
                return
            self.controller.load_playlist(name)  # loads + auto-plays
            self._notify(f"▶ {name}")
        elif lv_id == "track-list":
            path = getattr(event.item, "track_path", None)
            if not path:
                return
            self.controller.play_track(path)
            self._notify("▶ playing track")
        else:
            return
        self.refresh_now_playing()

    def _notify(self, msg: str) -> None:
        with contextlib.suppress(Exception):
            self.app.notify(escape(msg), timeout=2)

    # ---- transport actions (controller calls are crash-safe) ----
    def action_toggle(self) -> None:
        self.controller.toggle()
        self.refresh_now_playing()

    def action_next(self) -> None:
        self.controller.next()
        self.refresh_now_playing()

    def action_prev(self) -> None:
        self.controller.prev()
        self.refresh_now_playing()

    def action_seek_fwd(self) -> None:
        self.controller.seek(self._cfg.seek_seconds, relative=True, current=self._pos)
        self.refresh_now_playing()

    def action_seek_back(self) -> None:
        self.controller.seek(-self._cfg.seek_seconds, relative=True, current=self._pos)
        self.refresh_now_playing()

    def action_vol_up(self) -> None:
        self.controller.volume(self._cfg.volume_step_db)
        self.refresh_now_playing()

    def action_vol_down(self) -> None:
        self.controller.volume(-self._cfg.volume_step_db)
        self.refresh_now_playing()

    def action_shuffle(self) -> None:
        self.controller.shuffle("toggle")
        self.refresh_now_playing()

    def action_repeat(self) -> None:
        self.controller.repeat("cycle")
        self.refresh_now_playing()

    def action_refresh_all(self) -> None:
        self.refresh_view()
