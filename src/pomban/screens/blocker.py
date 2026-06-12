"""BlockerModal — log an interruption mid-focus.

Pushed by ``PomodoroApp.action_log_blocker`` when ``b`` is pressed during an
active focus session. Dismisses with the trimmed reason (Enter; empty string
counts as a blocker with no reason) or ``None`` (Esc) to abort. The app
callback writes the row via ``db.log_interruption`` and refreshes the
context header so the ``⚠ N today`` chip updates immediately.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class BlockerModal(ModalScreen[str | None]):
    DEFAULT_CSS = """
    BlockerModal { align: center middle; }
    BlockerModal > Center > Vertical {
        width: 64; height: auto;
        background: $surface;
        border: round $warning;
        padding: 1 2;
    }
    BlockerModal Input { margin-top: 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Center(), Vertical():
            yield Static(
                "[b yellow]⚠ Blocker[/]\n\nWhat blocked you? [dim](enter to log · esc to cancel)[/]"
            )
            yield Input(placeholder="e.g. noisy room, Slack ping, context switch")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss((event.value or "").strip())

    def action_cancel(self) -> None:
        self.dismiss(None)
