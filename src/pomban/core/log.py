"""Tiny file logger to the XDG state dir.

Safe to call while the TUI owns the terminal: it only ever writes to a file
(``~/.local/state/pomban/pomban.log``), never to stdout/stderr, which would
corrupt the alternate screen. Replaces scattered ``except Exception: pass`` that
swallowed all diagnostics.
"""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path

_logger: logging.Logger | None = None


def _state_dir() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state"))
    p = base / "pomban"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    log = logging.getLogger("pomban")
    log.setLevel(logging.INFO)
    log.propagate = False  # never bubble to the root/stderr handler
    if not log.handlers:
        try:
            handler = logging.FileHandler(_state_dir() / "pomban.log")
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            )
            log.addHandler(handler)
        except OSError:
            log.addHandler(logging.NullHandler())
    _logger = log
    return log


def exception(msg: str, *args: object) -> None:
    """Log an exception with traceback. Never raises."""
    with contextlib.suppress(Exception):
        get_logger().exception(msg, *args)


def warning(msg: str, *args: object) -> None:
    with contextlib.suppress(Exception):
        get_logger().warning(msg, *args)
