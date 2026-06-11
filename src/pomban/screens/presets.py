from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import ListItem, ListView, Static

from pomban.core.config import Preset


class PresetItem(ListItem):
    def __init__(self, preset: Preset) -> None:
        label = (
            f"[b]{preset.name}[/]  "
            f"[dim]{preset.focus_minutes}/{preset.short_break_minutes}/{preset.long_break_minutes}[/]"
        )
        super().__init__(Static(label))
        self.preset_data = preset


class PresetPicker(ModalScreen[Preset | None]):
    DEFAULT_CSS = """
    PresetPicker { align: center middle; }
    PresetPicker > Center > Vertical {
        width: 60; height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    """
    BINDINGS = [
        Binding("enter", "pick", "Select"),
        Binding("escape", "cancel", "Close"),
    ]

    def __init__(self, presets: list[Preset]) -> None:
        super().__init__()
        self.presets = presets

    def compose(self) -> ComposeResult:
        with Center(), Vertical():
            yield Static("[b]Choose a preset[/] [dim](enter to select, esc to cancel)[/]")
            lv = ListView(*[PresetItem(p) for p in self.presets])
            yield lv

    def action_pick(self) -> None:
        lv = self.query_one(ListView)
        if lv.index is None or not self.presets:
            self.dismiss(None)
            return
        child = lv.children[lv.index]
        if isinstance(child, PresetItem):
            self.dismiss(child.preset_data)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
