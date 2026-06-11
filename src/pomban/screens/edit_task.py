"""Modal to edit an existing task's title, tags, estimate, project, due, priority.

Returns a dict on save, or None on cancel:
  {"title": str, "tags": str, "estimate": int, "project": str,
   "due_date": str, "priority": int}
`tags` is comma-separated; `project` is a project name ("" clears the project);
`due_date` is ISO 'YYYY-MM-DD' or ''; `priority` is 0-3. The app layer resolves
the project name and writes via db.update_task.
"""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from pomban.core.models import Task


class EditTaskModal(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    EditTaskModal { align: center middle; }
    EditTaskModal > Center > Vertical {
        width: 60; height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    EditTaskModal Static.label { color: $text-muted; padding-top: 1; }
    EditTaskModal Input { margin-bottom: 0; }
    """

    BINDINGS = [
        Binding("enter", "save", "Save"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, task: Task, project_name: str | None = None) -> None:
        super().__init__()
        self.task_data = task
        self._project_name = project_name or ""

    def compose(self) -> ComposeResult:
        t = self.task_data
        with Center(), Vertical():
            yield Static("[b]Edit task[/] [dim](enter to save, esc to cancel)[/]")
            yield Static("Title", classes="label")
            yield Input(value=t.title, id="edit-title")
            yield Static("Tags [dim](comma-separated)[/]", classes="label")
            yield Input(value=(t.tags or "").replace(",", ", "), id="edit-tags")
            yield Static("Estimate [dim](pomodoros)[/]", classes="label")
            yield Input(value=str(t.estimated_pomodoros or 0), id="edit-estimate")
            yield Static("Project [dim](blank = Inbox)[/]", classes="label")
            yield Input(value=self._project_name, id="edit-project")
            yield Static("Due date [dim](YYYY-MM-DD, blank = none)[/]", classes="label")
            yield Input(value=t.due_date, id="edit-due", placeholder="2026-06-01")
            yield Static("Priority [dim](0 none · 1 low · 2 med · 3 high)[/]", classes="label")
            yield Input(value=str(t.priority or 0), id="edit-priority")

    def action_save(self) -> None:
        title = self.query_one("#edit-title", Input).value.strip()
        tags_raw = self.query_one("#edit-tags", Input).value
        estimate_raw = self.query_one("#edit-estimate", Input).value.strip()
        project = self.query_one("#edit-project", Input).value.strip()
        # Normalize tags: split on commas, strip, drop empties, rejoin CSV.
        tags = ",".join(t.strip() for t in tags_raw.split(",") if t.strip())
        try:
            estimate = max(0, int(estimate_raw)) if estimate_raw else 0
        except ValueError:
            estimate = self.task_data.estimated_pomodoros or 0
        if not title:
            title = self.task_data.title
        due_raw = self.query_one("#edit-due", Input).value.strip()
        due = ""
        if due_raw:
            try:
                from datetime import date as _date

                _date.fromisoformat(due_raw)
                due = due_raw
            except ValueError:
                due = self.task_data.due_date  # keep prior value on invalid input
        prio_raw = self.query_one("#edit-priority", Input).value.strip()
        try:
            priority = max(0, min(3, int(prio_raw))) if prio_raw else 0
        except ValueError:
            priority = self.task_data.priority or 0
        self.dismiss(
            {
                "title": title,
                "tags": tags,
                "estimate": estimate,
                "project": project,
                "due_date": due,
                "priority": priority,
            }
        )

    def action_cancel(self) -> None:
        self.dismiss(None)
