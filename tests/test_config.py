import tempfile
from pathlib import Path

from pomodoro.core import config as cfg_mod
from pomodoro.core.config import Config, Preset, load, save


def test_load_missing_file_returns_defaults():
    cfg = load("/tmp/definitely-does-not-exist-pomodoro.toml")
    assert cfg.timer.focus_minutes == 25
    assert cfg.ui.theme == "nord"
    assert cfg.presets == []


def test_round_trip(tmp_path):
    cfg = Config()
    cfg.timer.focus_minutes = 50
    cfg.ui.theme = "dracula"
    cfg.presets.append(Preset(name="deep", focus_minutes=50, short_break_minutes=10))
    p = tmp_path / "cfg.toml"
    save(cfg, p)
    loaded = load(p)
    assert loaded.timer.focus_minutes == 50
    assert loaded.ui.theme == "dracula"
    assert len(loaded.presets) == 1
    assert loaded.presets[0].name == "deep"


def test_invalid_theme_falls_back_to_default(tmp_path):
    p = tmp_path / "cfg.toml"
    p.write_text('[ui]\ntheme = "not-a-real-theme"\n')
    loaded = load(p)
    assert loaded.ui.theme == "nord"


def test_partial_file_uses_defaults_for_missing_sections(tmp_path):
    p = tmp_path / "cfg.toml"
    p.write_text("[timer]\nfocus_minutes = 45\n")
    loaded = load(p)
    assert loaded.timer.focus_minutes == 45
    assert loaded.timer.short_break_minutes == 5  # default
    assert loaded.ui.theme == "nord"  # default


def test_malformed_toml_returns_defaults(tmp_path):
    p = tmp_path / "broken.toml"
    p.write_text("this is not valid toml = = =")
    loaded = load(p)
    assert loaded.timer.focus_minutes == 25


def test_unknown_keys_are_dropped(tmp_path):
    p = tmp_path / "cfg.toml"
    p.write_text("[timer]\nfocus_minutes = 30\nold_removed_key = 99\n")
    loaded = load(p)
    assert loaded.timer.focus_minutes == 30


def test_to_settings_converts_minutes_to_seconds():
    cfg = Config()
    cfg.timer.focus_minutes = 25
    cfg.timer.short_break_minutes = 5
    settings = cfg_mod.to_settings(cfg)
    assert settings.focus_seconds == 25 * 60
    assert settings.short_break_seconds == 5 * 60
