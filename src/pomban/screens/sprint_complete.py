"""Non-blocking modal shown when the active sprint hits its pomodoro_target.

Three actions:

- ``c`` Close + retro — dismisses with ``"close_retro"``; the app routes to
  the sprint runner's RetroModal so the user files their retrospective.
- ``k`` Keep going — dismisses with ``"keep_going"``; nothing else changes.
- ``l`` Later — dismisses with ``"later"``; the modal also auto-dismisses
  to ``"later"`` after 8 seconds, so it never blocks the timer flow.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

AUTO_DISMISS_SECONDS = 8.0


class SprintCompleteModal(ModalScreen[str]):
    DEFAULT_CSS = """
    SprintCompleteModal { align: center middle; }
    SprintCompleteModal > Center > Vertical {
        width: 64; height: auto;
        background: $surface;
        border: round $success;
        padding: 1 2;
    }
    """
    BINDINGS = [
        Binding("c", "pick('close_retro')", "Close + retro", show=True),
        Binding("k", "pick('keep_going')", "Keep going", show=True),
        Binding("l,escape", "pick('later')", "Later", show=True),
    ]

    def __init__(self, sprint_name: str, completed: int, target: int) -> None:
        super().__init__()
        self._sprint_name = sprint_name
        self._completed = completed
        self._target = target

    def compose(self) -> ComposeResult:
        with Center(), Vertical():
            yield Static(
                f"[b green]Sprint target reached![/]\n\n"
                f"[b]{self._sprint_name}[/]  ·  {self._completed}/{self._target} 🍅\n\n"
                "[dim]c=close + retro   k=keep going   l=later[/]"
            )

    def on_mount(self) -> None:
        # Auto-dismiss so the user is never blocked from the next phase.
        self.set_timer(AUTO_DISMISS_SECONDS, self._auto_dismiss)

    def _auto_dismiss(self) -> None:
        # Guard against double-dismiss if the user already responded.
        if self.is_attached:
            self.dismiss("later")

    def action_pick(self, choice: str) -> None:
        self.dismiss(choice)
