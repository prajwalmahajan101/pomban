"""Modal for picking the active project filter.

Dismisses with:
  -1 → "All" (no filter)
   0 → Inbox (orphan tasks)
  >0 → project id
  None → cancelled
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import ListItem, ListView, Static

from pomodoro.core.models import Project


class _PickItem(ListItem):
    def __init__(self, value: int, label: str) -> None:
        super().__init__(Static(label))
        self.pick_value = value


class ProjectPickerModal(ModalScreen[int | None]):
    DEFAULT_CSS = """
    ProjectPickerModal { align: center middle; }
    ProjectPickerModal > Center > Vertical {
        width: 60; height: auto;
        max-height: 24;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    """
    BINDINGS = [
        Binding("enter", "pick", "Select"),
        Binding("escape", "cancel", "Close"),
    ]

    def __init__(self, projects: list[Project], current: int | None) -> None:
        super().__init__()
        self.projects = projects
        self.current = current

    def compose(self) -> ComposeResult:
        with Center(), Vertical():
            yield Static("[b]Filter by project[/]  [dim](enter to select, esc to cancel)[/]")
            items: list[_PickItem] = []
            items.append(_PickItem(-1, "[reverse white] All [/]  show every task"))
            items.append(_PickItem(0, "[reverse white] Inbox [/]  unfiled tasks"))
            for p in self.projects:
                items.append(_PickItem(p.id, f"[reverse {p.color}] {p.name} [/]"))
            yield ListView(*items)

    def action_pick(self) -> None:
        lv = self.query_one(ListView)
        if lv.index is None:
            self.dismiss(None)
            return
        child = lv.children[lv.index]
        if isinstance(child, _PickItem):
            self.dismiss(child.pick_value)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
