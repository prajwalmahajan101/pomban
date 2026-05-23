from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header


def _dur(secs: int) -> str:
    m, s = divmod(secs or 0, 60)
    return f"{m}m{s:02d}s"


class HistoryScreen(Screen):
    BINDINGS = [
        Binding("1", "app.switch('dashboard')", "Dashboard"),
        Binding("2", "app.switch('kanban')", "Kanban"),
        Binding("3", "app.switch('stats')", "Stats"),
        Binding("4", "app.switch('history')", "History"),
        Binding("question_mark", "app.help", "Help"),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DataTable(id="hist")
        yield Footer()

    def on_mount(self) -> None:
        table: DataTable = self.query_one("#hist", DataTable)
        table.add_columns("When", "Kind", "Planned", "Actual", "Done", "Interr.", "Task(s)")
        for row in self.app.db.session_history(100):
            table.add_row(
                row["started_at"][:16].replace("T", " "),
                row["kind"],
                _dur(row["planned_seconds"]),
                _dur(row["actual_seconds"]),
                "✓" if row["completed"] else "·",
                str(row["interruption_count"] or 0),
                row.get("task_titles") or "",
            )
