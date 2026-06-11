"""Block-character horizontal bar list. Renders [(label, value), ...] as colored bars."""

from __future__ import annotations

from textual.widgets import Static


def render_bars(
    data: list[tuple[str, int]],
    width: int = 30,
    colors: list[str] | None = None,
    value_suffix: str = "",
) -> str:
    if not data:
        return "[dim]no data[/]"
    max_v = max((v for _, v in data), default=0) or 1
    label_w = min(20, max((len(lbl) for lbl, _ in data), default=10))
    out = []
    for i, (lbl, v) in enumerate(data):
        bar_len = max(0, min(width, round(width * v / max_v)))
        color = colors[i] if colors and i < len(colors) else "cyan"
        bar = f"[{color}]" + ("█" * bar_len) + "[/]" + ("·" * (width - bar_len))
        out.append(f"  {lbl[:label_w]:<{label_w}}  {bar}  {v}{value_suffix}")
    return "\n".join(out)


class BarChart(Static):
    DEFAULT_CSS = """
    BarChart { height: auto; padding: 1 2; background: $panel; }
    """

    def set_data(
        self,
        data: list[tuple[str, int]],
        width: int = 30,
        colors: list[str] | None = None,
        value_suffix: str = "",
    ) -> None:
        self.update(render_bars(data, width=width, colors=colors, value_suffix=value_suffix))


def render_vertical_bars(data: list[tuple[str, int]], height: int = 6, color: str = "cyan") -> str:
    """Vertical block bar chart with labels along the bottom."""
    if not data:
        return "[dim]no data[/]"
    max_v = max((v for _, v in data), default=0) or 1
    glyphs = " ▁▂▃▄▅▆▇█"
    rows = []
    for r in range(height, 0, -1):
        line_chars = []
        for _, v in data:
            ratio = v / max_v
            cell_h = ratio * height
            if cell_h >= r:
                line_chars.append("█")
            elif cell_h > r - 1:
                frac = cell_h - (r - 1)
                idx = max(1, min(len(glyphs) - 1, int(frac * (len(glyphs) - 1))))
                line_chars.append(glyphs[idx])
            else:
                line_chars.append(" ")
        rows.append(f"[{color}]" + " ".join(line_chars) + "[/]")
    label_line = " ".join(lbl[:2] for lbl, _ in data)
    val_line = " ".join(f"{v:>2}" for _, v in data)
    return "\n".join(rows) + "\n" + label_line + "\n[dim]" + val_line + "[/]"


class VerticalBarChart(Static):
    DEFAULT_CSS = """
    VerticalBarChart { height: auto; padding: 1 2; background: $panel; }
    """

    def set_data(self, data: list[tuple[str, int]], height: int = 6, color: str = "cyan") -> None:
        self.update(render_vertical_bars(data, height=height, color=color))
