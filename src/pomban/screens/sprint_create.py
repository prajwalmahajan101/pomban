"""Modal for creating a sprint with the full field set.

Replaces the prior "single-line input" sprint creation flow (which only
captured a name + optional pomodoro target) with a structured modal that
collects the four sprint fields users actually plan against:

    name              required, defaults to ``"Sprint N"``
    pomodoro_target   integer, defaults to 0 (no target)
    duration_days     integer, defaults to 14
    goal              freeform text, optional

Dismisses with ``SprintCreateResult`` on submit or ``None`` on cancel.
The caller is responsible for persisting + activating the new sprint.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


@dataclass(frozen=True)
class SprintCreateResult:
    name: str
    pomodoro_target: int
    duration_days: int
    goal: str


class SprintCreateModal(ModalScreen[SprintCreateResult | None]):
    DEFAULT_CSS = """
    SprintCreateModal { align: center middle; }
    SprintCreateModal > Center > Vertical {
        width: 60; height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    SprintCreateModal .field-label {
        padding: 1 0 0 0;
        color: $text-muted;
    }
    SprintCreateModal .button-row { padding-top: 1; }
    SprintCreateModal Input { margin-bottom: 0; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Save"),
    ]

    def __init__(
        self,
        *,
        suggested_name: str = "Sprint 1",
        default_days: int = 14,
        default_target: int = 0,
    ) -> None:
        super().__init__()
        self._suggested_name = suggested_name
        self._default_days = default_days
        self._default_target = default_target

    def compose(self) -> ComposeResult:
        with Center(), Vertical():
            yield Static("[b]New sprint[/]  [dim](Ctrl+S save · Esc cancel)[/]")
            yield Static("Name", classes="field-label")
            yield Input(value=self._suggested_name, placeholder="Sprint name", id="sc-name")
            yield Static("Pomodoro target  [dim](0 = no target)[/]", classes="field-label")
            yield Input(
                value=str(self._default_target),
                placeholder="0",
                id="sc-target",
            )
            yield Static("Duration (days)", classes="field-label")
            yield Input(
                value=str(self._default_days),
                placeholder="14",
                id="sc-days",
            )
            yield Static("Goal  [dim](optional)[/]", classes="field-label")
            yield Input(value="", placeholder="What this sprint is for", id="sc-goal")
            with Center(classes="button-row"):
                yield Button("Create sprint", id="sc-submit", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#sc-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sc-submit":
            self.action_submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Enter on any field submits the modal — quick path for keyboard flow.
        self.action_submit()

    def action_submit(self) -> None:
        name = self.query_one("#sc-name", Input).value.strip()
        if not name:
            self.query_one("#sc-name", Input).focus()
            return
        try:
            target = int(self.query_one("#sc-target", Input).value.strip() or "0")
        except ValueError:
            target = 0
        try:
            days = int(self.query_one("#sc-days", Input).value.strip() or str(self._default_days))
        except ValueError:
            days = self._default_days
        goal = self.query_one("#sc-goal", Input).value.strip()
        self.dismiss(
            SprintCreateResult(
                name=name,
                pomodoro_target=max(0, target),
                duration_days=max(1, days),
                goal=goal,
            )
        )

    def action_cancel(self) -> None:
        self.dismiss(None)
