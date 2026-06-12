"""SprintRunnerScreen — overlay for the active sprint, bound to ``Shift+R``.

Header shows ``Sprint · <name> · M/N · D days left``. Body lists the sprint's
tasks with status + per-task completed pomodoros. Footer summarises bindings:

- ``Enter`` start focus on the highlighted task and switch to dashboard.
- ``c`` close + retro (push :class:`RetroModal`; on confirm, ``engine.close_sprint``).
- ``e`` edit retro (pre-fills existing text; calls ``engine.update_sprint_retro``).
- ``x``/``escape`` cancel and pop back.
"""

from __future__ import annotations

import contextlib

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Input, Static

from pomban.screens.base import AppScreen


class RetroModal(ModalScreen[str | None]):
    """Single-line input for sprint retrospective text.

    Dismisses with the trimmed string (Enter, may be empty) or ``None`` (Esc).
    Empty submissions still dismiss with ``""`` so close-without-retro is a
    deliberate choice rather than a silent cancel.
    """

    DEFAULT_CSS = """
    RetroModal { align: center middle; }
    RetroModal > Center > Vertical {
        width: 72; height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    RetroModal Input { margin-top: 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, prompt: str, initial: str = "") -> None:
        super().__init__()
        self._prompt = prompt
        self._initial = initial

    def compose(self) -> ComposeResult:
        with Center(), Vertical():
            yield Static(f"[b]{self._prompt}[/]\n[dim]enter to save · esc to cancel[/]")
            yield Input(value=self._initial, placeholder="What went well / what to change…")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss((event.value or "").strip())

    def action_cancel(self) -> None:
        self.dismiss(None)


class SprintRunnerScreen(AppScreen):
    CSS = """
    SprintRunnerScreen { layout: vertical; }
    #runner-summary { padding: 0 2; color: $text-muted; }
    #runner-help { dock: bottom; padding: 0 2; color: $text-muted; }
    """

    BINDINGS = [
        Binding("c", "close_with_retro", "Close + retro", show=True),
        Binding("e", "edit_retro", "Edit retro", show=True),
        Binding("x,escape", "cancel", "Close", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield from self.compose_header()
        yield Static("", id="runner-summary")
        yield DataTable(id="runner-tasks", cursor_type="row")
        yield Static(
            "[dim]enter=start focus  c=close+retro  e=edit retro  x=close[/]",
            id="runner-help",
        )
        yield Footer()

    def on_mount(self) -> None:
        table: DataTable = self.query_one("#runner-tasks", DataTable)
        table.add_columns("Status", "Title", "🍅", "Estimate")
        self.refresh_view()

    def refresh_view(self) -> None:
        super().refresh_view()
        self._refresh_summary()
        self._refresh_tasks()

    def _engine(self):
        return self.app._facade

    def _sprint_payload(self) -> dict | None:
        return self._engine().active_sprint_progress()

    def _refresh_summary(self) -> None:
        summary = self.query_one("#runner-summary", Static)
        payload = self._sprint_payload()
        if payload is None:
            summary.update("[red]No active sprint.[/] [dim]Press x to close.[/]")
            return
        sp = payload["sprint"]
        project = "Inbox"
        if sp.project_id is not None:
            try:
                project = self.app.db.get_project(sp.project_id).name
            except Exception:
                project = "?"
        target = payload["target"]
        completed = payload["completed"]
        days_left = payload["days_left"]
        tgt = f"{completed}/{target}" if target else f"{completed} 🍅"
        summary.update(f"[b]{sp.name}[/]  ·  [dim]{project}[/]  ·  {tgt}  ·  {days_left}d left")

    def _refresh_tasks(self) -> None:
        table: DataTable = self.query_one("#runner-tasks", DataTable)
        table.clear()
        payload = self._sprint_payload()
        if payload is None:
            return
        sp = payload["sprint"]
        for task in self._engine().sprint_tasks(sp.id):
            actual = self.app.db.task_actual_pomodoros(task.id)
            table.add_row(
                task.status,
                task.title,
                str(actual),
                str(task.estimated_pomodoros or 0),
                key=str(task.id),
            )

    def _selected_task_id(self) -> int | None:
        table: DataTable = self.query_one("#runner-tasks", DataTable)
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return None
        try:
            return int(row_key) if row_key else None
        except ValueError:
            return None

    # ---------- actions ----------
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Enter on a row → start focus on that task and switch to dashboard."""
        try:
            tid = int(event.row_key.value)
        except (ValueError, AttributeError):
            return
        try:
            task = self.app.db.get_task(tid)
        except Exception:
            return
        if self._engine().start_focus_on_many([task]):
            with contextlib.suppress(Exception):
                self.app.switch_screen("dashboard")

    def action_close_with_retro(self) -> None:
        payload = self._sprint_payload()
        if payload is None:
            return
        sp = payload["sprint"]
        self.app.push_screen(
            RetroModal("Sprint retrospective", initial=sp.retrospective or ""),
            lambda retro: self._on_close_retro(sp.id, retro),
        )

    def _on_close_retro(self, sprint_id: int, retro: str | None) -> None:
        if retro is None:
            return
        self._engine().close_sprint(sprint_id, retro)
        # Closing the sprint clears the active-sprint filter so headers update.
        self.app.set_active_sprint(None)
        with contextlib.suppress(Exception):
            self.notify("Sprint closed.", timeout=2)
        self.app.pop_screen()

    def action_edit_retro(self) -> None:
        payload = self._sprint_payload()
        if payload is None:
            return
        sp = payload["sprint"]
        self.app.push_screen(
            RetroModal("Edit retrospective", initial=sp.retrospective or ""),
            lambda retro: self._on_edit_retro(sp.id, retro),
        )

    def _on_edit_retro(self, sprint_id: int, retro: str | None) -> None:
        if retro is None:
            return
        self._engine().update_sprint_retro(sprint_id, retro)
        self.refresh_view()
        with contextlib.suppress(Exception):
            self.notify("Retro updated.", timeout=2)

    def action_cancel(self) -> None:
        self.app.pop_screen()
