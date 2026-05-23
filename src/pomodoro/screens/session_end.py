"""Modal shown when a Pomodoro phase completes.

Returns a dict describing the user's choice:
  {"action": "complete"}                — focus done, task done, advance
  {"action": "keep"}                    — focus done, task stays in Doing, advance
  {"action": "advance"}                 — break done, advance to focus
  {"action": "extend", "seconds": int}  — add time, stay in current phase
"""
from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from pomodoro.core.timer_engine import Phase


class SessionEndScreen(ModalScreen[dict]):
    DEFAULT_CSS = """
    SessionEndScreen { align: center middle; }
    SessionEndScreen > Center > Vertical {
        width: 60;
        height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    SessionEndScreen Static.title { content-align: center middle; padding-bottom: 1; }
    SessionEndScreen Static.body { padding-bottom: 1; }
    SessionEndScreen Static.hint { color: $text-muted; }
    """

    BINDINGS = [
        Binding("c", "complete", "Completed"),
        Binding("k", "keep", "Keep working on it"),
        Binding("enter", "default", "Continue"),
        Binding("e", "extend_menu", "Extend"),
        Binding("5", "extend(5)", "+5", show=False),
        Binding("0", "extend(10)", "+10", show=False),
        Binding("plus", "extend(15)", "+15", show=False),
        Binding("escape", "cancel", "Close", show=False),
    ]

    def __init__(self, completed_phase: Phase, task_title: Optional[str]) -> None:
        super().__init__()
        self.completed_phase = completed_phase
        self.task_title = task_title

    def compose(self) -> ComposeResult:
        was_focus_with_task = (
            self.completed_phase == Phase.FOCUS and self.task_title
        )
        if was_focus_with_task:
            title = "🍅 Focus session complete"
            body = (
                f"You worked on [b]{self.task_title}[/].\n"
                f"Did you finish it?\n\n"
                f"  [b]c[/]  Yes — mark done & take a break\n"
                f"  [b]k[/]  Not yet — keep in Doing & take a break\n"
                f"  [b]e[/]  Extend focus  ([dim]5/0/+ = +5/+10/+15 min[/])"
            )
        elif self.completed_phase == Phase.FOCUS:
            title = "🍅 Focus session complete"
            body = (
                "Nice work. Take a break.\n\n"
                "  [b]enter[/]  Start break\n"
                "  [b]e[/]      Extend focus  ([dim]5/0/+ = +5/+10/+15 min[/])"
            )
        else:
            label = "Short break" if self.completed_phase == Phase.SHORT_BREAK else "Long break"
            title = f"⏰ {label} over"
            body = (
                "Ready for the next focus session?\n\n"
                "  [b]enter[/]  Start focus\n"
                "  [b]e[/]      Extend break ([dim]5/0/+ = +5/+10/+15 min[/])"
            )
        with Center():
            with Vertical():
                yield Static(title, classes="title")
                yield Static(body, classes="body")
                yield Static("[dim]esc closes — phase will stay paused[/]", classes="hint")

    def action_complete(self) -> None:
        self.dismiss({"action": "complete"})

    def action_keep(self) -> None:
        self.dismiss({"action": "keep"})

    def action_default(self) -> None:
        if self.completed_phase == Phase.FOCUS and self.task_title:
            # In the focus-with-task modal, "enter" isn't a primary action — ignore.
            return
        self.dismiss({"action": "advance"})

    def action_extend(self, minutes: int) -> None:
        self.dismiss({"action": "extend", "seconds": minutes * 60})

    def action_extend_menu(self) -> None:
        # The hint already documents 5/0/+ — leaving menu inline keeps it one keystroke deep.
        pass

    def action_cancel(self) -> None:
        self.dismiss(None)
