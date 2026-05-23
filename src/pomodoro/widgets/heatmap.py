"""Pure renderer: list of (date, minutes) → unicode block-character bar chart string."""
from __future__ import annotations

from textual.widgets import Static

BLOCKS = ["·", "░", "▒", "▓", "█"]


def render_heatmap(data: list[tuple[str, int]], cell_per_step: int = 30) -> str:
    """Render as one row, day labels above, blocks below.

    cell_per_step: minutes that take you to the next density block.
    """
    if not data:
        return "[dim]no data[/]"
    labels = "  ".join(d[5:] for d, _ in data)   # MM-DD
    cells = []
    for _, mins in data:
        idx = min(len(BLOCKS) - 1, mins // cell_per_step)
        cells.append(BLOCKS[idx])
    cells_str = "  " + "    ".join(cells)
    minutes_line = " ".join(f"{m:>4}" for _, m in data)
    return f"{labels}\n{cells_str}\n{minutes_line}"


class Heatmap(Static):
    DEFAULT_CSS = """
    Heatmap {
        height: auto;
        padding: 1 2;
        background: $panel;
    }
    """

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self.update(render_heatmap(data))
