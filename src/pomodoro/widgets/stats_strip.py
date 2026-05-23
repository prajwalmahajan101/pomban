from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class StatsStrip(Static):
    sessions: reactive[int] = reactive(0)
    focus_seconds: reactive[int] = reactive(0)
    streak: reactive[int] = reactive(0)

    DEFAULT_CSS = """
    StatsStrip {
        height: 3;
        padding: 0 2;
        background: $boost;
        content-align: center middle;
    }
    """

    def render(self) -> str:
        mins = self.focus_seconds // 60
        return (
            f"[b]{self.sessions}[/] sessions today   "
            f"[b]{mins}[/] focus min   "
            f"[b]🔥 {self.streak}[/] day streak"
        )
