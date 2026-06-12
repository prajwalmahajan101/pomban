"""Tests for M4 working-hours notification suppression."""

from __future__ import annotations

from datetime import datetime, time
from unittest.mock import patch

from pomban.core.config import BreaksSection, Config, to_notify_config
from pomban.notifications import NotifyConfig, fire, within_working_hours


def test_default_config_has_no_window():
    cfg = NotifyConfig()
    assert cfg.working_hours is None
    # Without a window, always permissive.
    assert within_working_hours(cfg, datetime(2026, 6, 12, 3, 0)) is True
    assert within_working_hours(cfg, datetime(2026, 6, 12, 14, 0)) is True


def test_simple_daytime_window():
    cfg = NotifyConfig(working_hours=(time(9, 0), time(17, 0)))
    assert within_working_hours(cfg, datetime(2026, 6, 12, 8, 59)) is False
    assert within_working_hours(cfg, datetime(2026, 6, 12, 9, 0)) is True
    assert within_working_hours(cfg, datetime(2026, 6, 12, 12, 30)) is True
    assert within_working_hours(cfg, datetime(2026, 6, 12, 17, 0)) is True
    assert within_working_hours(cfg, datetime(2026, 6, 12, 17, 1)) is False


def test_overnight_window_wraps_midnight():
    cfg = NotifyConfig(working_hours=(time(22, 0), time(6, 0)))
    assert within_working_hours(cfg, datetime(2026, 6, 12, 23, 0)) is True
    assert within_working_hours(cfg, datetime(2026, 6, 12, 5, 0)) is True
    assert within_working_hours(cfg, datetime(2026, 6, 12, 10, 0)) is False


def test_fire_skips_desktop_and_sound_outside_window():
    cfg = NotifyConfig(working_hours=(time(9, 0), time(17, 0)))
    with (
        patch("pomban.notifications.desktop") as mock_desktop,
        patch("pomban.notifications.play_sound") as mock_play,
        patch("pomban.notifications.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = datetime(2026, 6, 12, 22, 0)
        fire("title", "body", cfg)
        mock_desktop.assert_not_called()
        mock_play.assert_not_called()


def test_fire_calls_desktop_and_sound_inside_window():
    cfg = NotifyConfig(working_hours=(time(9, 0), time(17, 0)))
    with (
        patch("pomban.notifications.desktop") as mock_desktop,
        patch("pomban.notifications.play_sound") as mock_play,
        patch("pomban.notifications.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = datetime(2026, 6, 12, 10, 0)
        fire("title", "body", cfg)
        mock_desktop.assert_called_once_with("title", "body")
        mock_play.assert_called_once()


def test_to_notify_config_parses_hhmm_window():
    cfg = Config()
    cfg.breaks = BreaksSection(working_hours_start="09:00", working_hours_end="17:00")
    notify = to_notify_config(cfg)
    assert notify.working_hours == (time(9, 0), time(17, 0))


def test_to_notify_config_skips_window_when_unset():
    cfg = Config()
    notify = to_notify_config(cfg)
    assert notify.working_hours is None


def test_to_notify_config_ignores_malformed_window():
    cfg = Config()
    cfg.breaks = BreaksSection(working_hours_start="not-a-time", working_hours_end="17:00")
    notify = to_notify_config(cfg)
    assert notify.working_hours is None
