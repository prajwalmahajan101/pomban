"""Modal for picking the active project filter.

Dismisses with:
  -1 → "All" (no filter)
   0 → Inbox (orphan tasks)
  >0 → project id
  None → cancelled
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import ListItem, ListView, Static

if TYPE_CHECKING:
    from pomban.core.models import Project


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
            yield ListView(*items, initial_index=0)

    def on_mount(self) -> None:
        self.query_one(ListView).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, _PickItem):
            self.dismiss(event.item.pick_value)
        else:
            self.dismiss(None)

    def action_pick(self) -> None:
        lv = self.query_one(ListView)
        idx = lv.index if lv.index is not None else 0
        if not lv.children:
            self.dismiss(None)
            return
        child = lv.children[idx]
        if isinstance(child, _PickItem):
            self.dismiss(child.pick_value)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
