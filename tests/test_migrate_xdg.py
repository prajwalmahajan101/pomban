"""Migration shim: legacy ``pomodoro`` XDG dirs rename to ``pomban`` on startup."""

from __future__ import annotations

from pathlib import Path

from pomban._migrate_xdg import migrate


def _seed_old(base: Path, name: str, files: list[str]) -> Path:
    p = base / name
    p.mkdir(parents=True)
    for f in files:
        (p / f).write_text("seed")
    return p


def test_migrate_renames_data_state_config(tmp_path, monkeypatch):
    data = tmp_path / "data"
    state = tmp_path / "state"
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))

    _seed_old(data, "pomodoro", ["pomodoro.db"])
    _seed_old(state, "pomodoro", ["pomodoro.log", "hooks.log"])
    _seed_old(config, "pomodoro", ["config.toml"])

    migrate()

    assert (data / "pomban" / "pomban.db").exists()
    assert not (data / "pomodoro").exists()
    assert (state / "pomban" / "pomban.log").exists()
    assert (state / "pomban" / "hooks.log").exists()
    assert (config / "pomban" / "config.toml").exists()


def test_migrate_noop_when_new_exists(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "s"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "c"))

    _seed_old(data, "pomodoro", ["pomodoro.db"])
    (data / "pomban").mkdir()
    (data / "pomban" / "pomban.db").write_text("existing")

    migrate()

    assert (data / "pomodoro" / "pomodoro.db").exists()  # untouched
    assert (data / "pomban" / "pomban.db").read_text() == "existing"


def test_migrate_noop_when_old_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "d"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "s"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "c"))
    migrate()  # must not raise
