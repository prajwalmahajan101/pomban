from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, Static

from pomodoro.core.models import Task
from pomodoro.screens.base import AppScreen
from pomodoro.widgets.card import TaskCard


COLUMNS = ("todo", "doing", "done")
COLUMN_LABEL = {"todo": "To Do", "doing": "Doing", "done": "Done"}


def _project_info(app, task: Task) -> tuple[str | None, str | None]:
    """Resolve (project_name, project_color) for a task."""
    if task.project_id is None:
        return None, None
    try:
        p = app.db.get_project(task.project_id)
        return p.name, p.color
    except Exception:
        return None, None


def _sprint_name(app, task: Task) -> str | None:
    if task.sprint_id is None:
        return None
    try:
        return app.db.get_sprint(task.sprint_id).name
    except Exception:
        return None


class KanbanScreen(AppScreen):
    CSS = """
    KanbanScreen { layout: vertical; }
    #board { height: 1fr; }
    .column {
        width: 1fr;
        border: round $primary-darken-1;
        margin: 0 1;
        padding: 0 1;
    }
    .column.-active-col { border: round $accent; }
    .column.-active-col > .column-title { background: $accent; color: $text; text-style: bold; }
    .column-title { background: $panel; padding: 0 1; }
    .column-body { height: 1fr; }
    #kanban-input { dock: bottom; }
    """

    BINDINGS = [
        Binding("h", "cursor_left", "←", show=False),
        Binding("l", "cursor_right", "→", show=False),
        Binding("tab", "cursor_right", "Next col", show=False),
        Binding("shift+tab", "cursor_left", "Prev col", show=False),
        Binding("j", "cursor_down", "↓", show=False),
        Binding("k", "cursor_up", "↑", show=False),
        Binding("shift+h,H,<,comma", "move_card_left", "Move ←"),
        Binding("shift+l,L,>,.", "move_card_right", "Move →"),
        Binding("shift+j,J,]", "reorder_down", "▼"),
        Binding("shift+k,K,[", "reorder_up", "▲"),
        Binding("o", "reopen", "Reopen"),
        Binding("n", "new_card", "New"),
        Binding("d,x", "delete_card", "Delete"),
        Binding("c", "complete_card", "Done"),
        Binding("e", "app.edit_task", "Edit"),
        Binding("v", "toggle_visual", "Select"),
        Binding("space", "toggle_select", "Toggle", show=False),
        Binding("enter,s", "start_focus", "Focus"),
        Binding("1", "app.switch('dashboard')", "Dashboard"),
        Binding("2", "app.switch('kanban')", "Kanban"),
        Binding("3", "app.switch('stats')", "Stats", show=False),
        Binding("4", "app.switch('history')", "History", show=False),
        Binding("5", "app.switch('projects')", "Projects", show=False),
        Binding("6", "app.switch('sprints')", "Sprints", show=False),
        Binding("question_mark", "app.help", "Help"),
        Binding("t", "app.cycle_theme", "Theme"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # cursor: column index 0..2, row index within that column
        self.col = 0
        self.row = 0
        # Multi-task visual select (Mode B): toggle with `v`, pick cards with Space.
        self.visual_mode = False
        self.selected_ids: set[int] = set()

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

    def refresh_view(self) -> None:
        self.refresh_board()

    # ---------- render ----------
    def refresh_board(self) -> None:
        pf = self.app.project_filter_for_db()
        groups = self.app.db.list_tasks_by_status(project_filter=pf)
        # Apply sprint filter on top if set
        sprint_id = self.app.active_sprint_id
        for status in COLUMNS:
            body = self.query_one(f"#body-{status}", VerticalScroll)
            body.remove_children()
            tasks = groups.get(status, [])
            if sprint_id is not None:
                tasks = [t for t in tasks if t.sprint_id == sprint_id]
            for t in tasks:
                pname, pcolor = _project_info(self.app, t)
                sname = _sprint_name(self.app, t)
                actual = self.app.db.task_actual_pomodoros(t.id)
                body.mount(TaskCard(t, project_name=pname, project_color=pcolor,
                                    sprint_name=sname, actual_pomodoros=actual))
            title = self.query_one(f"#title-{status}", Static)
            title.update(f"[b]{COLUMN_LABEL[status]}[/] ({len(tasks)})")
        # Update header to show active filter
        try:
            label = self.app.active_project_label()
            sprint_label = None
            if sprint_id is not None:
                try:
                    sprint_label = self.app.db.get_sprint(sprint_id).name
                except Exception:
                    sprint_label = None
            tag_parts = []
            if label:
                tag_parts.append(f"[reverse {self.app.active_project_color()}] {label} [/]")
            if sprint_label:
                tag_parts.append(f"[bright_yellow]▸ {sprint_label}[/]")
            extra = "  ".join(tag_parts)
            try:
                self.sub_title = label or ""
            except Exception:
                pass
        except Exception:
            pass
        self._clamp_cursor()
        self._paint_cursor()

    def _column_tasks(self, col_idx: int) -> list[Task]:
        status = COLUMNS[col_idx]
        pf = self.app.project_filter_for_db()
        tasks = self.app.db.list_tasks(status=status, project_filter=pf)
        if self.app.active_sprint_id is not None:
            tasks = [t for t in tasks if t.sprint_id == self.app.active_sprint_id]
        return tasks

    def _clamp_cursor(self) -> None:
        n = len(self._column_tasks(self.col))
        if n == 0:
            self.row = 0
        else:
            self.row = max(0, min(self.row, n - 1))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Context-sensitive keymap: which actions apply depends on the active column.

        Returning False hides the binding from the Footer, so the visible keymap
        changes as you move between To Do / Doing / Done (lazydocker-style).
        """
        if action == "move_card_left":
            return self.col > 0
        if action == "move_card_right":
            return self.col < len(COLUMNS) - 1
        if action == "start_focus":
            return COLUMNS[self.col] != "done"   # focusing a done task is meaningless
        if action == "complete_card":
            return COLUMNS[self.col] != "done"   # already done
        if action == "reopen":
            return COLUMNS[self.col] == "done"   # only Done can be reopened
        return True

    def _paint_cursor(self) -> None:
        for i, status in enumerate(COLUMNS):
            self.query_one(f"#col-{status}", Vertical).set_class(i == self.col, "-active-col")
            body = self.query_one(f"#body-{status}", VerticalScroll)
            for card in body.query(TaskCard):
                card.remove_class("-focused")
                card.set_class(card.task_data.id in self.selected_ids, "-selected")
        focused = self.focused_card()
        if focused:
            focused.add_class("-focused")
            focused.scroll_visible()
        # The visible footer keymap depends on the active column — refresh it.
        self.refresh_bindings()

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

    def action_reopen(self) -> None:
        """Done → To Do. Only meaningful on the Done column (see check_action)."""
        card = self.focused_card()
        if not card or COLUMNS[self.col] != "done":
            return
        self.app.db.move_task(card.task_data.id, "todo")
        self.refresh_board()

    def action_toggle_visual(self) -> None:
        self.visual_mode = not self.visual_mode
        if not self.visual_mode:
            self.selected_ids.clear()
        try:
            self.app.notify(
                "Visual select: Space to pick, s/Enter to focus the batch"
                if self.visual_mode else "Visual select off",
                timeout=2,
            )
        except Exception:
            pass
        self._paint_cursor()

    def action_toggle_select(self) -> None:
        if not self.visual_mode:
            return
        card = self.focused_card()
        if not card:
            return
        tid = card.task_data.id
        if tid in self.selected_ids:
            self.selected_ids.discard(tid)
        else:
            self.selected_ids.add(tid)
        self._paint_cursor()

    def _selected_tasks(self) -> list[Task]:
        """Collect Task objects for selected ids, preserving board order."""
        out: list[Task] = []
        for status in COLUMNS:
            body = self.query_one(f"#body-{status}", VerticalScroll)
            for card in body.query(TaskCard):
                if card.task_data.id in self.selected_ids:
                    out.append(card.task_data)
        return out

    def action_start_focus(self) -> None:
        if self.visual_mode and self.selected_ids:
            tasks = self._selected_tasks()
            self.visual_mode = False
            self.selected_ids.clear()
            self.app.start_focus_on_many(tasks)
            return
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
