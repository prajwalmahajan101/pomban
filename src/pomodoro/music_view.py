"""Shared helpers for rendering external-player ('cliamp') now-playing state.

Both the compact dashboard ``MusicPanel`` and the full ``MusicScreen`` read the
player's ``status --json`` (an unknown-ish shape) and turn it into display
strings. Keeping the extraction + formatting here avoids duplicating the
defensive parsing and the markup-safety: every player-supplied string is escaped
before it goes into Rich markup, and every color goes through ``adapt`` so it
degrades under NO_COLOR / low-color terminals.
"""

from __future__ import annotations

import re

from rich.markup import escape

from pomodoro.core.colors import adapt


def _as_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract(status: dict) -> dict:
    """Pull display fields out of an unknown-shape status dict, defensively.

    Returns a superset of what the panel/screen need; missing fields come back as
    ``None`` / ``""`` / ``False`` so callers can render unconditionally. The track
    info may be nested under one of a few common keys.
    """
    track = status
    for key in ("track", "now_playing", "current", "song"):
        if isinstance(status.get(key), dict):
            track = status[key]
            break

    def first(d, *keys):
        for k in keys:
            v = d.get(k)
            if v not in (None, ""):
                return v
        return None

    title = first(track, "title", "name", "track") or first(status, "title", "name")
    artist = first(track, "artist", "author", "uploader") or first(status, "artist")
    album = first(track, "album") or first(status, "album")
    state = (first(status, "state", "status", "playback") or "").lower()
    # Playing state: prefer an explicit boolean, fall back to a state string.
    playing = status.get("playing")
    if playing is None:
        playing = state in ("playing", "play", "started")
    volume = first(status, "volume", "vol", "volume_db")
    position = _as_float(
        first(track, "position", "elapsed", "time") or first(status, "position", "elapsed", "time")
    )
    duration = _as_float(
        first(track, "duration", "length", "total") or first(status, "duration", "length", "total")
    )
    shuffle = bool(status.get("shuffle"))
    repeat = str(first(status, "repeat", "repeat_mode", "loop") or "").lower()
    speed = _as_float(first(status, "speed", "rate"))
    index = first(status, "index", "track_index", "queue_index")
    return {
        "title": title,
        "artist": artist,
        "album": album,
        "playing": bool(playing),
        "state": state,
        "volume": volume,
        "position": position,
        "duration": duration,
        "shuffle": shuffle,
        "repeat": repeat,
        "speed": speed,
        "index": index,
    }


def fmt_mmss(seconds) -> str:
    """Format seconds as ``m:ss`` (or ``h:mm:ss``); ``--:--`` when unknown."""
    if seconds is None:
        return "--:--"
    try:
        s = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        return "--:--"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def render_progress_bar(position, duration, *, width: int = 30, color: str = "cyan") -> str:
    """A ``mm:ss [####----] mm:ss`` bar; dims to a placeholder without a duration."""
    width = max(4, int(width))
    left, right = fmt_mmss(position), fmt_mmss(duration)
    dur, pos = _as_float(duration), _as_float(position)
    if not dur or dur <= 0 or pos is None:
        return f"[dim]{left} / {right}[/]"
    frac = max(0.0, min(1.0, pos / dur))
    filled = round(frac * width)
    bar = "█" * filled + "─" * (width - filled)
    c = adapt(color)
    bar = f"[{c}]{bar}[/]" if c else bar
    return f"{left} {bar} {right}"


def now_playing_lines(info: dict) -> tuple[str, str]:
    """(title_line, meta_line) — both fully escaped and markup-safe."""
    title = info.get("title")
    if title:
        line1 = f"[b]{escape(str(title))}[/]"
    else:
        st = info.get("state") or ("playing" if info.get("playing") else "idle")
        line1 = f"[b]{escape(str(st))}[/]"
    bits = []
    if info.get("artist"):
        bits.append(escape(str(info["artist"])))
    if info.get("album"):
        bits.append(escape(str(info["album"])))
    return line1, "  ·  ".join(bits)


def flags_line(info: dict) -> str:
    """Status glyphs: play state · shuffle · repeat · volume · speed (escaped)."""
    parts = ["▶" if info.get("playing") else "⏸"]
    if info.get("shuffle"):
        parts.append("⤮ shuffle")
    rep = info.get("repeat")
    if rep and rep not in ("off", "none", "0"):
        parts.append(f"↻ {escape(str(rep))}")
    vol = info.get("volume")
    if vol is not None:
        parts.append(f"vol {escape(str(vol))}")
    sp = info.get("speed")
    if sp and abs(sp - 1.0) > 0.01:
        parts.append(f"{sp:g}×")
    return "  ·  ".join(parts)


_NUM_PREFIX = re.compile(r"^\d+[.)]\s*")
# cliamp lists playlists column-aligned as "Name        N tracks"; strip that suffix
# (2+ spaces guards against eating a single-space name word).
_TRACK_COUNT_SUFFIX = re.compile(r"\s{2,}\d+\s+tracks?\s*$", re.IGNORECASE)


def parse_playlists(text: str) -> list[str]:
    """Best-effort parse of ``cliamp playlist list`` text into playlist names.

    cliamp's text output isn't a stable contract, so this is tolerant: it drops
    blank/header lines, trims a leading bullet or ``N.`` number, and strips a
    trailing ``" (12 tracks)"`` annotation. Worst case the labels are slightly
    off — it never raises.
    """
    names: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.lower().startswith(("playlists", "name", "no playlists", "usage", "error")):
            continue
        for prefix in ("• ", "* ", "- "):
            if line.startswith(prefix):
                line = line[len(prefix) :].strip()
        line = _NUM_PREFIX.sub("", line)
        line = _TRACK_COUNT_SUFFIX.sub("", line)  # "Name   12 tracks" → "Name"
        cut = line.rfind(" (")
        if cut > 0 and line.endswith(")"):
            line = line[:cut].strip()  # "Name (12 tracks)" → "Name"
        line = line.strip()
        if line:
            names.append(line)
    return names
