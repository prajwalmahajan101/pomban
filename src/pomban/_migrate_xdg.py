"""One-shot XDG directory rename from the legacy ``pomodoro`` name to ``pomban``.

Runs at startup before any DB/log/config read. No-op if the new path already
exists or the old path does not. Swallows OSError (logging is not yet
initialised here — falls back to stderr).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOTS = [
    ("XDG_DATA_HOME", ".local/share"),
    ("XDG_STATE_HOME", ".local/state"),
    ("XDG_CONFIG_HOME", ".config"),
]


def migrate() -> None:
    for env, default in _ROOTS:
        base = Path(os.environ.get(env) or str(Path.home() / default))
        old, new = base / "pomodoro", base / "pomban"
        if not old.exists() or new.exists():
            continue
        try:
            old.rename(new)
        except OSError as exc:
            sys.stderr.write(f"pomban: could not migrate {old} -> {new}: {exc}\n")
            continue
        for stem in ("pomodoro.db", "pomodoro.log"):
            f = new / stem
            if f.exists():
                target = new / stem.replace("pomodoro", "pomban")
                try:
                    f.rename(target)
                except OSError as exc:
                    sys.stderr.write(f"pomban: could not rename {f}: {exc}\n")
