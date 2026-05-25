"""One-line block sparkline."""
from __future__ import annotations

from textual.widgets import Static

BLOCKS = " ▁▂▃▄▅▆▇█"


def render_sparkline(values: list[float], color: str = "cyan",
                      target_line: float | None = None) -> str:
    if not values:
        return "[dim]—[/]"
    finite = [v for v in values if v == v]  # filter NaN
    if not finite:
        return "[dim]—[/]"
    lo = min(finite + ([target_line] if target_line is not None else []))
    hi = max(finite + ([target_line] if target_line is not None else []))
    rng = (hi - lo) or 1.0
    out = []
    for v in values:
        ratio = (v - lo) / rng
        idx = max(0, min(len(BLOCKS) - 1, int(ratio * (len(BLOCKS) - 1))))
        out.append(BLOCKS[idx])
    return f"[{color}]" + "".join(out) + "[/]"


class Sparkline(Static):
    DEFAULT_CSS = "Sparkline { height: 1; padding: 0 1; }"

    def set_values(self, values: list[float], color: str = "cyan",
                   target_line: float | None = None) -> None:
        self.update(render_sparkline(values, color=color, target_line=target_line))
