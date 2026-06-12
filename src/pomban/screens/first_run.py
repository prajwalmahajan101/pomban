"""First-run modal: empty-DB launch prompts for an initial project name.

Pushed by ``PomodoroApp.on_mount`` when ``engine.is_first_run()`` returns
True. Dismisses with the trimmed project name on Enter, or ``None`` if the
user escapes (the app falls back to leaving the library empty — Inbox stays
available).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class FirstRunModal(ModalScreen[str | None]):
    DEFAULT_CSS = """
    FirstRunModal { align: center middle; }
    FirstRunModal > Center > Vertical {
        width: 64; height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    FirstRunModal Input { margin-top: 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "Skip"),
    ]

    def compose(self) -> ComposeResult:
        with Center(), Vertical():
            yield Static(
                "[b]Welcome to pomban[/]\n\n"
                "Name your first project to get started.\n"
                "[dim]enter to create · esc to skip[/]"
            )
            yield Input(placeholder="e.g. Personal", id="first-run-name")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        name = (event.value or "").strip()
        self.dismiss(name or None)

    def action_cancel(self) -> None:
        self.dismiss(None)
