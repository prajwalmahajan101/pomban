from __future__ import annotations

import contextlib

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Input, Static

from pomodoro.screens.base import AppScreen

COLOR_CYCLE = [
    "cyan",
    "green",
    "yellow",
    "magenta",
    "blue",
    "red",
    "bright_cyan",
    "bright_green",
    "bright_yellow",
    "bright_magenta",
    "white",
]


class ProjectsScreen(AppScreen):
    CSS = """
    ProjectsScreen { layout: vertical; }
    #proj-input { dock: bottom; }
    #proj-help { color: $text-muted; padding: 0 2; }
    """

    BINDINGS = [
        Binding("n", "new_project", "New", show=True),
        Binding("r", "rename", "Rename", show=True),
        Binding("c", "recolor", "Color", show=True),
        Binding("a", "archive", "Archive", show=True),
        Binding("d,x", "delete", "Delete", show=True),
        Binding("enter", "filter_by", "Filter & open kanban"),
        Binding("escape", "blur_input", "", show=False),
        Binding("1", "app.switch('dashboard')", "Dashboard"),
        Binding("2", "app.switch('kanban')", "Kanban"),
        Binding("3", "app.switch('stats')", "Stats"),
        Binding("4", "app.switch('history')", "History"),
        Binding("5", "app.switch('projects')", "Projects"),
        Binding("6", "app.switch('sprints')", "Sprints"),
        Binding("question_mark", "app.help", "Help"),
        Binding("t", "app.cycle_theme", "Theme"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._mode: str | None = None  # None | "new" | "rename"
        self._target_id: int | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "[b]Projects[/]  [dim]n=new  r=rename  c=recolor  a=archive  d=delete  enter=filter[/]",
            id="proj-help",
        )
        yield DataTable(id="proj-table", cursor_type="row")
        yield Input(placeholder="(press n to add or r to rename)", id="proj-input")
        yield Footer()

    def on_mount(self) -> None:
        table: DataTable = self.query_one("#proj-table", DataTable)
        table.add_columns("Color", "Name", "To Do", "Doing", "Done", "🍅", "Status")
        self.refresh_projects()

    def refresh_view(self) -> None:
        self.refresh_projects()

    def refresh_projects(self) -> None:
        table: DataTable = self.query_one("#proj-table", DataTable)
        table.clear()
        for p in self.app.db.list_projects(include_archived=True):
            counts = self.app.db.project_task_counts(p.id)
            an = self.app.db.project_analytics(p.id)
            actual = an.get("actual_pomodoros", 0)
            status = "archived" if p.archived else ""
            table.add_row(
                f"[reverse {p.color}]    [/]",
                p.name,
                str(counts["todo"]),
                str(counts["doing"]),
                str(counts["done"]),
                str(actual),
                status,
                key=str(p.id),
            )
        # Also append the Inbox row at the end (synthetic, no id)
        counts = self.app.db.project_task_counts(None)
        table.add_row(
            "[reverse white]    [/]",
            "Inbox (orphan)",
            str(counts["todo"]),
            str(counts["doing"]),
            str(counts["done"]),
            "—",
            "",
            key="inbox",
        )

    def _selected_project_id(self) -> int | None:
        table: DataTable = self.query_one("#proj-table", DataTable)
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return None
        if not row_key or row_key == "inbox":
            return None
        try:
            return int(row_key)
        except ValueError:
            return None

    # ---------- actions ----------
    def action_new_project(self) -> None:
        self._mode = "new"
        inp = self.query_one("#proj-input", Input)
        inp.placeholder = "New project name (Enter to add, Esc to cancel)"
        inp.value = ""
        inp.focus()

    def action_rename(self) -> None:
        pid = self._selected_project_id()
        if pid is None:
            return
        p = self.app.db.get_project(pid)
        self._mode = "rename"
        self._target_id = pid
        inp = self.query_one("#proj-input", Input)
        inp.placeholder = f"Rename '{p.name}' to:"
        inp.value = p.name
        inp.focus()

    def action_recolor(self) -> None:
        pid = self._selected_project_id()
        if pid is None:
            return
        p = self.app.db.get_project(pid)
        try:
            idx = COLOR_CYCLE.index(p.color)
        except ValueError:
            idx = -1
        new_color = COLOR_CYCLE[(idx + 1) % len(COLOR_CYCLE)]
        self.app.db.update_project(pid, color=new_color)
        self.refresh_projects()
        with contextlib.suppress(Exception):
            self.notify(f"{p.name} → {new_color}", timeout=2)

    def action_archive(self) -> None:
        pid = self._selected_project_id()
        if pid is None:
            return
        p = self.app.db.get_project(pid)
        self.app.db.archive_project(pid, not p.archived)
        self.refresh_projects()

    def action_delete(self) -> None:
        pid = self._selected_project_id()
        if pid is None:
            return
        counts = self.app.db.project_task_counts(pid)
        total = counts["todo"] + counts["doing"] + counts["done"]
        # If active filter is on this project, clear it
        if self.app.project_filter.scoped_project_id == pid:
            self.app.set_active_project(None)
        self.app.db.delete_project(pid, move_tasks_to_inbox=True)
        self.refresh_projects()
        try:
            if total:
                self.notify(f"Deleted project; {total} tasks moved to Inbox.", timeout=3)
        except Exception:
            pass

    def action_filter_by(self) -> None:
        pid = self._selected_project_id()
        if pid is None:
            # Inbox row → set Inbox filter
            table: DataTable = self.query_one("#proj-table", DataTable)
            try:
                row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            except Exception:
                return
            if row_key == "inbox":
                from pomodoro.core.filters import ProjectFilter

                self.app.set_project_filter(ProjectFilter.inbox())
            else:
                return
        else:
            self.app.set_active_project(pid)
        with contextlib.suppress(Exception):
            self.app.switch_screen("kanban")

    def action_blur_input(self) -> None:
        self._mode = None
        self._target_id = None
        inp = self.query_one("#proj-input", Input)
        inp.value = ""
        inp.placeholder = "(press n to add or r to rename)"
        self.query_one("#proj-table", DataTable).focus()

    # ---------- input ----------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "proj-input":
            return
        text = event.value.strip()
        if not text:
            self.action_blur_input()
            return
        if self._mode == "new":
            self.app.db.get_or_create_project(text)
        elif self._mode == "rename" and self._target_id is not None:
            try:
                self.app.db.update_project(self._target_id, name=text)
            except Exception as e:
                with contextlib.suppress(Exception):
                    self.notify(f"Rename failed: {e}", timeout=3, severity="error")
        self.action_blur_input()
        self.refresh_projects()
