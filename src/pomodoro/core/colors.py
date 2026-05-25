"""Color helpers: deterministic palette indexing + NO_COLOR / low-color downgrade.

Two concerns:

* ``stable_index`` — pick a palette slot from a string deterministically. The old
  code used the builtin ``hash()``, which is salted per process (PYTHONHASHSEED),
  so a project/tag changed color on every launch. ``crc32`` is stable.
* ``adapt`` / ``paint`` — honor https://no-color.org/ and degrade the 256-color
  ``bright_*`` names to their 16-color base on terminals that don't advertise 256
  colors.
"""
from __future__ import annotations

import os
import zlib


def stable_index(s: str, n: int) -> int:
    """Deterministic index in ``[0, n)`` from a string, stable across processes."""
    if n <= 0:
        return 0
    return zlib.crc32(s.encode("utf-8")) % n


_BRIGHT_FALLBACK = {
    "bright_red": "red", "bright_green": "green", "bright_yellow": "yellow",
    "bright_blue": "blue", "bright_magenta": "magenta", "bright_cyan": "cyan",
    "bright_black": "bright_black", "bright_white": "white",
}


def no_color() -> bool:
    """True when NO_COLOR is set to any non-empty value."""
    return bool(os.environ.get("NO_COLOR"))


def _low_color() -> bool:
    if os.environ.get("COLORTERM") in ("truecolor", "24bit"):
        return False
    return "256" not in os.environ.get("TERM", "")


def adapt(color: str) -> str:
    """Adapt a Rich color name to the environment.

    Returns ``""`` when colors are disabled (NO_COLOR), else downgrades
    ``bright_*`` names on low-color terminals.
    """
    if no_color():
        return ""
    if _low_color() and color in _BRIGHT_FALLBACK:
        return _BRIGHT_FALLBACK[color]
    return color


def paint(text: str, color: str) -> str:
    """Wrap ``text`` in Rich color markup, or return it bare under NO_COLOR."""
    c = adapt(color)
    return f"[{c}]{text}[/]" if c else text
