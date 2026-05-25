"""Modal shown when a Pomodoro phase completes.

Returns a dict describing the user's choice:
  {"action": "complete"}                — focus done, task done, advance
  {"action": "complete_multi"}          — multi-task focus done; app asks which to mark done
  {"action": "keep"}                    — focus done, task stays in Doing, advance
  {"action": "advance"}                 — break done, advance to focus
  {"action": "extend", "seconds": int}  — add time, stay in current phase
  {"action": "lunch"}                   — take a lunch break (LONG_PAUSE)
"""
from __future__ import annotations

from typing import Optional

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import ListItem, ListView, Static

from pomodoro.core.models import Task
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
        Binding("l", "lunch", "Lunch"),
        Binding("5", "extend(5)", "+5", show=False),
        Binding("0", "extend(10)", "+10", show=False),
        Binding("plus", "extend(15)", "+15", show=False),
        Binding("escape", "cancel", "Close", show=False),
    ]

    def __init__(self, completed_phase: Phase, task_title: Optional[str],
                 suggest_lunch: bool = False, lunch_minutes: int = 45,
                 multi_tasks: Optional[list[Task]] = None) -> None:
        super().__init__()
        self.completed_phase = completed_phase
        self.task_title = task_title
        self.suggest_lunch = suggest_lunch
        self.lunch_minutes = lunch_minutes
        self.multi_tasks = multi_tasks

    def compose(self) -> ComposeResult:
        is_multi = self.completed_phase == Phase.FOCUS and self.multi_tasks
        was_focus_with_task = (
            self.completed_phase == Phase.FOCUS and self.task_title and not is_multi
        )
        if is_multi:
            title = "🍅 Focus session complete"
            names = ", ".join(escape(t.title) for t in self.multi_tasks)
            body = (
                f"You worked on [b]{len(self.multi_tasks)}[/] tasks: [dim]{names}[/]\n\n"
                f"  [b]c[/]  Choose which are done\n"
                f"  [b]k[/]  None done yet — keep all in Doing & take a break\n"
                f"  [b]e[/]  Extend focus  ([dim]5/0/+ = +5/+10/+15 min[/])"
            )
        elif was_focus_with_task:
            title = "🍅 Focus session complete"
            body = (
                f"You worked on [b]{escape(self.task_title)}[/].\n"
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
        if self.suggest_lunch:
            body += f"\n  [b]l[/]  Take lunch ({self.lunch_minutes}m)"
        with Center():
            with Vertical():
                yield Static(title, classes="title")
                yield Static(body, classes="body")
                yield Static("[dim]esc closes — phase will stay paused[/]", classes="hint")

    def action_complete(self) -> None:
        if self.completed_phase == Phase.FOCUS and self.multi_tasks:
            self.dismiss({"action": "complete_multi"})
        else:
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

    def action_lunch(self) -> None:
        self.dismiss({"action": "lunch"})

    def action_extend_menu(self) -> None:
        # The hint already documents 5/0/+ — leaving menu inline keeps it one keystroke deep.
        pass

    def action_cancel(self) -> None:
        self.dismiss(None)


class _MultiItem(ListItem):
    def __init__(self, task: Task, checked: bool) -> None:
        self.task_id = task.id
        self.checked = checked
        self._title = task.title
        super().__init__(Static(self._label()))

    def _label(self) -> str:
        box = "[x]" if self.checked else "[ ]"
        return f"{box} {escape(self._title)}"

    def toggle(self) -> None:
        self.checked = not self.checked
        self.query_one(Static).update(self._label())


class MultiCompleteModal(ModalScreen[list]):
    """Pick which of a multi-task session's tasks to mark done. Returns a list of ids."""
    DEFAULT_CSS = """
    MultiCompleteModal { align: center middle; }
    MultiCompleteModal > Center > Vertical {
        width: 60; height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    MultiCompleteModal ListView { height: auto; max-height: 12; }
    """
    BINDINGS = [
        Binding("space", "toggle", "Toggle"),
        Binding("y", "all", "All done"),
        Binding("n", "none", "None"),
        Binding("enter", "confirm", "Confirm"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, tasks: list[Task]) -> None:
        super().__init__()
        self.tasks = tasks

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical():
                yield Static("[b]Which tasks did you finish?[/] "
                             "[dim](space toggles · y=all · n=none · enter confirms)[/]")
                yield ListView(*[_MultiItem(t, checked=True) for t in self.tasks])

    def action_toggle(self) -> None:
        lv = self.query_one(ListView)
        if lv.index is None:
            return
        child = lv.children[lv.index]
        if isinstance(child, _MultiItem):
            child.toggle()

    def action_all(self) -> None:
        self.dismiss([t.id for t in self.tasks])

    def action_none(self) -> None:
        self.dismiss([])

    def action_confirm(self) -> None:
        ids = [c.task_id for c in self.query(_MultiItem) if c.checked]
        self.dismiss(ids)

    def action_cancel(self) -> None:
        # Cancel = nothing marked done (tasks stay in Doing).
        self.dismiss([])
