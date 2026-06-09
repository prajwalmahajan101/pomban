"""Read-focused detail view for a kanban card.

Surfaces everything a card hides: full (scrollable) notes plus tags, project,
sprint, priority, due date, and pomodoro progress. It doesn't edit in place —
``e`` dismisses with an "edit" action so the caller can reuse the existing
``EditTaskModal``; ``c`` completes; ``p`` cycles priority. Dismisses with a small
action dict (or None) the kanban screen acts on.
"""

from __future__ import annotations

from typing import Optional

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from pomodoro.core.models import Task
from pomodoro.widgets.card import (
    PRIORITY_LABELS,
    STATUS_MARK,
    render_chips,
    render_due,
    render_priority,
    render_project_badge,
    render_sprint_chip,
)


class CardDetailScreen(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    CardDetailScreen { align: center middle; }
    CardDetailScreen > Center > Vertical {
        width: 72; max-height: 90%;
        background: $surface; border: round $primary; padding: 1 2;
    }
    CardDetailScreen .detail-notes {
        height: auto; max-height: 18;
        border: round $primary-darken-2; padding: 0 1; margin-top: 1;
    }
    CardDetailScreen Static.dlabel { color: $text-muted; padding-top: 1; }
    """

    BINDINGS = [
        Binding("escape,q", "close", "Close"),
        Binding("e", "edit", "Edit"),
        Binding("c", "complete", "Done"),
        Binding("p", "cycle_priority", "Priority"),
    ]

    def __init__(
        self,
        task: Task,
        *,
        project_name: str | None = None,
        project_color: str | None = None,
        sprint_name: str | None = None,
        actual_pomodoros: int = 0,
    ) -> None:
        super().__init__()
        self.task_data = task
        self.project_name = project_name
        self.project_color = project_color
        self.sprint_name = sprint_name
        self.actual_pomodoros = actual_pomodoros

    def compose(self) -> ComposeResult:
        t = self.task_data
        with Center(), Vertical():
            yield Static(self._header())
            yield Static(self._meta())
            yield Static("Notes", classes="dlabel")
            with VerticalScroll(classes="detail-notes"):
                notes = (t.notes or "").strip()
                yield Static(escape(notes) if notes else "[dim]No notes — press e to edit[/]")
            yield Static("[dim]e edit · c done · p priority · esc close[/]", classes="dlabel")

    def _header(self) -> str:
        t = self.task_data
        prio = render_priority(t.priority)
        prefix = f"{prio} " if prio else ""
        badge = render_project_badge(self.project_name, self.project_color)
        return f"{prefix}{badge} {STATUS_MARK[t.status]} [b]{escape(t.title)}[/]"

    def _meta(self) -> str:
        t = self.task_data
        parts = []
        chips = render_chips(t.tags)
        if chips:
            parts.append(chips)
        sprint = render_sprint_chip(self.sprint_name)
        if sprint:
            parts.append(sprint)
        plabel = PRIORITY_LABELS.get(t.priority or 0, "")
        if plabel:
            parts.append(f"[dim]priority:[/] {escape(plabel)}")
        if t.due_date:
            parts.append(f"[dim]due:[/] {render_due(t.due_date)}")
        if t.estimated_pomodoros:
            parts.append(f"🍅 {self.actual_pomodoros}/{t.estimated_pomodoros}")
        return "  ·  ".join(parts) if parts else "[dim]no tags, due date, or estimate[/]"

    def action_close(self) -> None:
        self.dismiss(None)

    def action_edit(self) -> None:
        self.dismiss({"action": "edit"})

    def action_complete(self) -> None:
        self.dismiss({"action": "complete"})

    def action_cycle_priority(self) -> None:
        self.dismiss({"action": "priority", "value": ((self.task_data.priority or 0) + 1) % 4})
