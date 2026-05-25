"""Modal for picking the active sprint filter.

Dismisses with:
  -1 → "All" (no sprint filter)
  >0 → sprint id
  None → cancelled
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import ListItem, ListView, Static

from pomodoro.core.models import Sprint


class _PickItem(ListItem):
    def __init__(self, value: int, label: str) -> None:
        super().__init__(Static(label))
        self.pick_value = value


class SprintPickerModal(ModalScreen[int | None]):
    DEFAULT_CSS = """
    SprintPickerModal { align: center middle; }
    SprintPickerModal > Center > Vertical {
        width: 70; height: auto; max-height: 24;
        background: $surface; border: round $primary; padding: 1 2;
    }
    """
    BINDINGS = [
        Binding("enter", "pick", "Select"),
        Binding("escape", "cancel", "Close"),
    ]

    def __init__(self, sprints: list[Sprint], current: int | None) -> None:
        super().__init__()
        self.sprints = sprints
        self.current = current

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical():
                yield Static("[b]Filter by sprint[/]  [dim](enter to select, esc to cancel)[/]")
                items: list[_PickItem] = [_PickItem(-1, "[dim] All sprints (no filter) [/]")]
                if not self.sprints:
                    items.append(_PickItem(-1, "[dim italic] no sprints yet — press 6 to create one [/]"))
                for sp in self.sprints:
                    marker = "▶" if sp.status == "active" else "·"
                    items.append(_PickItem(
                        sp.id,
                        f"{marker} [b]{sp.name}[/]  [dim]{sp.start_date} → {sp.end_date}  ({sp.status})[/]"
                    ))
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
