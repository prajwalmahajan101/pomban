from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static

from pomodoro.core.models import Task
from pomodoro.widgets.card import TaskCard


COLUMNS = ("todo", "doing", "done")
COLUMN_LABEL = {"todo": "To Do", "doing": "Doing", "done": "Done"}


class KanbanScreen(Screen):
    CSS = """
    KanbanScreen { layout: vertical; }
    #board { height: 1fr; }
    .column {
        width: 1fr;
        border: round $primary-darken-1;
        margin: 0 1;
        padding: 0 1;
    }
    .column-title { background: $panel; padding: 0 1; }
    .column-body { height: 1fr; }
    #kanban-input { dock: bottom; }
    """

    BINDINGS = [
        Binding("h", "cursor_left", "←", show=False),
        Binding("l", "cursor_right", "→", show=False),
        Binding("j", "cursor_down", "↓", show=False),
        Binding("k", "cursor_up", "↑", show=False),
        Binding("shift+h,H,<,comma", "move_card_left", "Move ←"),
        Binding("shift+l,L,>,.", "move_card_right", "Move →"),
        Binding("shift+j,J,]", "reorder_down", "▼"),
        Binding("shift+k,K,[", "reorder_up", "▲"),
        Binding("n", "new_card", "New"),
        Binding("d,x", "delete_card", "Delete"),
        Binding("c", "complete_card", "Done"),
        Binding("enter,s", "start_focus", "Focus"),
        Binding("1", "app.switch('dashboard')", "Dashboard"),
        Binding("2", "app.switch('kanban')", "Kanban"),
        Binding("3", "app.switch('stats')", "Stats", show=False),
        Binding("4", "app.switch('history')", "History", show=False),
        Binding("question_mark", "app.help", "Help"),
        Binding("t", "app.cycle_theme", "Theme"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # cursor: column index 0..2, row index within that column
        self.col = 0
        self.row = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="board"):
            for status in COLUMNS:
                with Vertical(classes="column", id=f"col-{status}"):
                    yield Static(f"[b]{COLUMN_LABEL[status]}[/]", classes="column-title",
                                 id=f"title-{status}")
                    yield VerticalScroll(classes="column-body", id=f"body-{status}")
        yield Input(placeholder="New card title — use #tag inline (Enter to add)",
                    id="kanban-input")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_board()
        self.query_one("#kanban-input", Input).can_focus = True

    # ---------- render ----------
    def refresh_board(self) -> None:
        groups = self.app.db.list_tasks_by_status()
        for status in COLUMNS:
            body = self.query_one(f"#body-{status}", VerticalScroll)
            body.remove_children()
            tasks = groups.get(status, [])
            for t in tasks:
                body.mount(TaskCard(t))
            title = self.query_one(f"#title-{status}", Static)
            title.update(f"[b]{COLUMN_LABEL[status]}[/] ({len(tasks)})")
        self._clamp_cursor()
        self._paint_cursor()

    def _column_tasks(self, col_idx: int) -> list[Task]:
        status = COLUMNS[col_idx]
        return self.app.db.list_tasks(status=status)

    def _clamp_cursor(self) -> None:
        n = len(self._column_tasks(self.col))
        if n == 0:
            self.row = 0
        else:
            self.row = max(0, min(self.row, n - 1))

    def _paint_cursor(self) -> None:
        for status in COLUMNS:
            body = self.query_one(f"#body-{status}", VerticalScroll)
            for card in body.query(TaskCard):
                card.remove_class("-focused")
        focused = self.focused_card()
        if focused:
            focused.add_class("-focused")
            focused.scroll_visible()

    def focused_card(self) -> TaskCard | None:
        body = self.query_one(f"#body-{COLUMNS[self.col]}", VerticalScroll)
        cards = list(body.query(TaskCard))
        if not cards:
            return None
        return cards[min(self.row, len(cards) - 1)]

    # ---------- navigation ----------
    def action_cursor_left(self) -> None:
        if self.col > 0:
            self.col -= 1
            self._clamp_cursor()
            self._paint_cursor()

    def action_cursor_right(self) -> None:
        if self.col < len(COLUMNS) - 1:
            self.col += 1
            self._clamp_cursor()
            self._paint_cursor()

    def action_cursor_down(self) -> None:
        n = len(self._column_tasks(self.col))
        if self.row < n - 1:
            self.row += 1
            self._paint_cursor()

    def action_cursor_up(self) -> None:
        if self.row > 0:
            self.row -= 1
            self._paint_cursor()

    # ---------- card ops ----------
    def action_move_card_left(self) -> None:
        card = self.focused_card()
        if not card or self.col == 0:
            return
        new_status = COLUMNS[self.col - 1]
        self.app.db.move_task(card.task_data.id, new_status)
        self.col -= 1
        self.refresh_board()

    def action_move_card_right(self) -> None:
        card = self.focused_card()
        if not card or self.col == len(COLUMNS) - 1:
            return
        new_status = COLUMNS[self.col + 1]
        self.app.db.move_task(card.task_data.id, new_status)
        self.col += 1
        self.refresh_board()

    def action_reorder_up(self) -> None:
        if self.row == 0:
            return
        tasks = self._column_tasks(self.col)
        self.app.db.swap_positions(tasks[self.row].id, tasks[self.row - 1].id)
        self.row -= 1
        self.refresh_board()

    def action_reorder_down(self) -> None:
        tasks = self._column_tasks(self.col)
        if self.row >= len(tasks) - 1:
            return
        self.app.db.swap_positions(tasks[self.row].id, tasks[self.row + 1].id)
        self.row += 1
        self.refresh_board()

    def action_new_card(self) -> None:
        self.query_one("#kanban-input", Input).focus()

    def action_delete_card(self) -> None:
        card = self.focused_card()
        if not card:
            return
        self.app.delete_task_by_id(card.task_data.id)
        self.refresh_board()

    def action_complete_card(self) -> None:
        card = self.focused_card()
        if not card:
            return
        self.app.db.move_task(card.task_data.id, "done")
        self.refresh_board()

    def action_start_focus(self) -> None:
        card = self.focused_card()
        if not card:
            return
        self.app.start_focus_on(card.task_data)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "kanban-input":
            return
        title = event.value.strip()
        if not title:
            return
        # Add into the currently-focused column.
        task = self.app.add_task_from_input(title)
        target_status = COLUMNS[self.col]
        if target_status != "todo":
            self.app.db.move_task(task.id, target_status)
        event.input.value = ""
        self.refresh_board()
        # Move cursor to the new card
        tasks = self._column_tasks(self.col)
        for i, t in enumerate(tasks):
            if t.id == task.id:
                self.row = i
                break
        self._paint_cursor()
