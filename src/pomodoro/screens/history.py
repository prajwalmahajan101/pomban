from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header

from pomodoro.screens.base import AppScreen


def _dur(secs: int) -> str:
    m, s = divmod(secs or 0, 60)
    return f"{m}m{s:02d}s"


class HistoryScreen(AppScreen):
    BINDINGS = [
        Binding("1", "app.switch('dashboard')", "Dashboard"),
        Binding("2", "app.switch('kanban')", "Kanban"),
        Binding("3", "app.switch('stats')", "Stats"),
        Binding("4", "app.switch('history')", "History"),
        Binding("5", "app.switch('projects')", "Projects", show=False),
        Binding("6", "app.switch('sprints')", "Sprints", show=False),
        Binding("question_mark", "app.help", "Help"),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DataTable(id="hist")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_history()

    def refresh_view(self) -> None:
        self.refresh_history()

    def refresh_history(self) -> None:
        table: DataTable = self.query_one("#hist", DataTable)
        try:
            table.clear(columns=True)
        except TypeError:
            table.clear()
        table.add_columns(
            "When", "Kind", "Project(s)", "Planned", "Actual", "Done", "Interr.", "Task(s)"
        )
        active_pid = self.app.project_filter.scoped_project_id
        for row in self.app.db.session_history(100, project_id=active_pid):
            table.add_row(
                row["started_at"][:16].replace("T", " "),
                row["kind"],
                row.get("projects") or "",
                _dur(row["planned_seconds"]),
                _dur(row["actual_seconds"]),
                "✓" if row["completed"] else "·",
                str(row["interruption_count"] or 0),
                row.get("task_titles") or "",
            )
