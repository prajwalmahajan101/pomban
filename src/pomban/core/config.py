"""TOML config loader. Lives at $XDG_CONFIG_HOME/pomban/config.toml (default ~/.config/pomban/)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path


def default_config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "pomban"


def default_config_path() -> Path:
    return default_config_dir() / "config.toml"


VALID_THEMES = (
    "nord",
    "gruvbox",
    "dracula",
    "catppuccin-mocha",
    "tokyo-night",
    "textual-dark",
    "textual-light",
)


@dataclass
class TimerSection:
    focus_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    cycles_before_long_break: int = 4
    warning_seconds: int = 30
    auto_advance: bool = False


@dataclass
class NotifySection:
    desktop: bool = True
    sound: bool = True
    bell_and_flash: bool = True
    sound_file: str | None = None


@dataclass
class UISection:
    theme: str = "nord"
    mouse: bool = False


@dataclass
class HooksSection:
    on_focus_start: str | None = None
    on_focus_end: str | None = None
    on_break_start: str | None = None
    on_break_end: str | None = None


@dataclass
class SyncSection:
    enabled: bool = False


@dataclass
class BreaksSection:
    lunch_minutes: int = 45
    lunch_window_start: str = ""  # "HH:MM" — empty disables the suggestion
    lunch_window_end: str = ""
    # Outside this window, desktop popups + sound are suppressed (bell/flash
    # still fire). Empty strings disable the gate.
    working_hours_start: str = ""
    working_hours_end: str = ""


@dataclass
class KanbanSection:
    # Per-column work-in-progress limits; 0 = unlimited. A column over its limit is
    # flagged on the board (warns on move, doesn't hard-block).
    wip_todo: int = 0
    wip_doing: int = 0
    wip_done: int = 0


@dataclass
class Preset:
    name: str
    focus_minutes: int
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    cycles_before_long_break: int = 4


@dataclass
class Config:
    timer: TimerSection = field(default_factory=TimerSection)
    notifications: NotifySection = field(default_factory=NotifySection)
    ui: UISection = field(default_factory=UISection)
    hooks: HooksSection = field(default_factory=HooksSection)
    sync: SyncSection = field(default_factory=SyncSection)
    breaks: BreaksSection = field(default_factory=BreaksSection)
    kanban: KanbanSection = field(default_factory=KanbanSection)
    presets: list[Preset] = field(default_factory=list)


def _filter_kwargs(cls, data: dict) -> dict:
    """Drop unknown keys so renamed/removed config keys don't crash the loader."""
    fields = set(cls.__dataclass_fields__.keys())
    return {k: v for k, v in data.items() if k in fields}


def load(path: Path | str | None = None) -> Config:
    p = Path(path) if path else default_config_path()
    if not p.exists():
        return Config()
    try:
        raw = tomllib.loads(p.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return Config()

    cfg = Config()
    if isinstance(raw.get("timer"), dict):
        cfg.timer = TimerSection(**_filter_kwargs(TimerSection, raw["timer"]))
    if isinstance(raw.get("notifications"), dict):
        cfg.notifications = NotifySection(**_filter_kwargs(NotifySection, raw["notifications"]))
    if isinstance(raw.get("ui"), dict):
        ui_data = _filter_kwargs(UISection, raw["ui"])
        if "theme" in ui_data and ui_data["theme"] not in VALID_THEMES:
            ui_data.pop("theme")
        cfg.ui = UISection(**ui_data)
    if isinstance(raw.get("hooks"), dict):
        cfg.hooks = HooksSection(**_filter_kwargs(HooksSection, raw["hooks"]))
    if isinstance(raw.get("sync"), dict):
        cfg.sync = SyncSection(**_filter_kwargs(SyncSection, raw["sync"]))
    if isinstance(raw.get("breaks"), dict):
        cfg.breaks = BreaksSection(**_filter_kwargs(BreaksSection, raw["breaks"]))
    if isinstance(raw.get("kanban"), dict):
        cfg.kanban = KanbanSection(**_filter_kwargs(KanbanSection, raw["kanban"]))
    presets = raw.get("preset", [])
    if isinstance(presets, list):
        cfg.presets = [
            Preset(**_filter_kwargs(Preset, p))
            for p in presets
            if isinstance(p, dict) and "name" in p and "focus_minutes" in p
        ]
    return cfg


def save(cfg: Config, path: Path | str | None = None) -> None:
    p = Path(path) if path else default_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for section_name, section in (
        ("timer", cfg.timer),
        ("notifications", cfg.notifications),
        ("ui", cfg.ui),
        ("hooks", cfg.hooks),
        ("sync", cfg.sync),
        ("breaks", cfg.breaks),
        ("kanban", cfg.kanban),
    ):
        lines.append(f"[{section_name}]")
        for k, v in asdict(section).items():
            lines.append(_format_kv(k, v))
        lines.append("")
    for preset in cfg.presets:
        lines.append("[[preset]]")
        for k, v in asdict(preset).items():
            lines.append(_format_kv(k, v))
        lines.append("")
    p.write_text("\n".join(lines))


def _format_kv(k: str, v) -> str:
    if v is None:
        return f"# {k} = ..."
    if isinstance(v, bool):
        return f"{k} = {'true' if v else 'false'}"
    if isinstance(v, int | float):
        return f"{k} = {v}"
    return f'{k} = "{v}"'


def to_settings(cfg: Config):
    """Build a TimerEngine Settings from this config."""
    from pomban.core.timer_engine import Settings

    return Settings(
        focus_seconds=cfg.timer.focus_minutes * 60,
        short_break_seconds=cfg.timer.short_break_minutes * 60,
        long_break_seconds=cfg.timer.long_break_minutes * 60,
        cycles_before_long_break=cfg.timer.cycles_before_long_break,
        warning_seconds=cfg.timer.warning_seconds,
    )


def _parse_hhmm(s: str):
    from datetime import time

    if not s:
        return None
    try:
        h, m = s.split(":", 1)
        return time(int(h), int(m))
    except (ValueError, TypeError):
        return None


def to_notify_config(cfg: Config):
    from pomban.notifications import NotifyConfig

    start = _parse_hhmm(cfg.breaks.working_hours_start)
    end = _parse_hhmm(cfg.breaks.working_hours_end)
    window = (start, end) if (start is not None and end is not None) else None
    return NotifyConfig(
        desktop=cfg.notifications.desktop,
        bell=cfg.notifications.bell_and_flash,
        sound=cfg.notifications.sound,
        sound_file=cfg.notifications.sound_file,
        working_hours=window,
    )
