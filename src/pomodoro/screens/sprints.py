from __future__ import annotations

from datetime import date, timedelta

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from pomodoro.screens.base import AppScreen
from textual.widgets import DataTable, Footer, Header, Input, Static


class SprintsScreen(AppScreen):
    CSS = """
    SprintsScreen { layout: vertical; }
    #sprint-input { dock: bottom; }
    #sprint-help { color: $text-muted; padding: 0 2; }
    """

    BINDINGS = [
        Binding("n", "new_sprint", "New", show=True),
        Binding("a", "activate", "Activate", show=True),
        Binding("c", "complete", "Complete", show=True),
        Binding("x", "cancel_sprint", "Cancel", show=True),
        Binding("d", "delete", "Delete", show=True),
        Binding("e", "edit_target", "Edit target", show=True),
        Binding("g", "edit_goal", "Edit goal", show=True),
        Binding("enter", "filter_by", "Filter & open kanban", show=False),
        Binding("escape", "blur_input", "", show=False),
        Binding("1", "app.switch('dashboard')", "Dashboard"),
        Binding("2", "app.switch('kanban')", "Kanban"),
        Binding("3", "app.switch('stats')", "Stats"),
        Binding("4", "app.switch('history')", "History"),
        Binding("5", "app.switch('projects')", "Projects"),
        Binding("6", "app.switch('sprints')", "Sprints"),
        Binding("question_mark", "app.help", "Help"),
        Binding("t", "app.cycle_theme", "Theme"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._mode: str | None = None
        self._target_id: int | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("[b]Sprints[/]  [dim]n=new  a=activate  c=complete  x=cancel  d=delete  e=target  g=goal  enter=filter[/]",
                     id="sprint-help")
        yield DataTable(id="sprint-table", cursor_type="row")
        yield Input(placeholder="(press n to add a new sprint)", id="sprint-input")
        yield Footer()

    def on_mount(self) -> None:
        table: DataTable = self.query_one("#sprint-table", DataTable)
        table.add_columns("Status", "Project", "Name", "Range", "Progress", "Days left", "Goal")
        self.refresh_sprints()

    def refresh_view(self) -> None:
        self.refresh_sprints()

    def refresh_sprints(self) -> None:
        table: DataTable = self.query_one("#sprint-table", DataTable)
        table.clear()
        sprints = self.app.db.list_sprints()
        for sp in sprints:
            try:
                proj = self.app.db.get_project(sp.project_id) if sp.project_id else None
                pname = proj.name if proj else "Inbox"
                pcolor = proj.color if proj else "white"
            except Exception:
                pname, pcolor = "?", "white"
            bd = self.app.db.sprint_burndown(sp.id)
            done = bd["completed"]
            target = sp.pomodoro_target or 0
            pct = (100 * done // target) if target else 0
            progress = f"{done}/{target} ({pct}%)" if target else f"{done}/—"
            try:
                end = date.fromisoformat(sp.end_date)
                days_left = max(0, (end - date.today()).days)
                if sp.status in ("completed", "cancelled"):
                    days_left_s = "—"
                else:
                    days_left_s = str(days_left)
            except Exception:
                days_left_s = "?"
            status_mark = {"active": "▶ active", "planned": "· planned",
                           "completed": "✓ done", "cancelled": "x cancelled"}.get(sp.status, sp.status)
            table.add_row(
                status_mark,
                f"[reverse {pcolor}] {pname} [/]",
                sp.name,
                f"{sp.start_date} → {sp.end_date}",
                progress,
                days_left_s,
                (sp.goal or "")[:40],
                key=str(sp.id),
            )

    def _selected_sprint_id(self) -> int | None:
        table: DataTable = self.query_one("#sprint-table", DataTable)
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return None
        if not row_key:
            return None
        try:
            return int(row_key)
        except ValueError:
            return None

    def action_new_sprint(self) -> None:
        self._mode = "new"
        inp = self.query_one("#sprint-input", Input)
        # Default to active project, else None
        scope = "current project" if self.app.project_filter.is_project else "Inbox"
        inp.placeholder = f"name [target_pomodoros] (default 14d, project={scope}) — Esc to cancel"
        inp.value = ""
        inp.focus()

    def action_activate(self) -> None:
        sid = self._selected_sprint_id()
        if sid is None:
            return
        self.app.db.activate_sprint(sid)
        self.app.set_active_sprint(sid)
        self.refresh_sprints()
        try:
            sp = self.app.db.get_sprint(sid)
            self.notify(f"Activated sprint '{sp.name}'", timeout=2)
        except Exception:
            pass

    def action_complete(self) -> None:
        sid = self._selected_sprint_id()
        if sid is None:
            return
        # Could open retrospective modal; for now just set status.
        self.app.db.update_sprint(sid, status="completed")
        if self.app.active_sprint_id == sid:
            self.app.set_active_sprint(None)
        self.refresh_sprints()

    def action_cancel_sprint(self) -> None:
        sid = self._selected_sprint_id()
        if sid is None:
            return
        self.app.db.update_sprint(sid, status="cancelled")
        if self.app.active_sprint_id == sid:
            self.app.set_active_sprint(None)
        self.refresh_sprints()

    def action_delete(self) -> None:
        sid = self._selected_sprint_id()
        if sid is None:
            return
        if self.app.active_sprint_id == sid:
            self.app.set_active_sprint(None)
        self.app.db.delete_sprint(sid)
        self.refresh_sprints()

    def action_edit_target(self) -> None:
        sid = self._selected_sprint_id()
        if sid is None:
            return
        self._mode = "target"
        self._target_id = sid
        sp = self.app.db.get_sprint(sid)
        inp = self.query_one("#sprint-input", Input)
        inp.placeholder = f"New pomodoro target for '{sp.name}' (current: {sp.pomodoro_target})"
        inp.value = str(sp.pomodoro_target or "")
        inp.focus()

    def action_edit_goal(self) -> None:
        sid = self._selected_sprint_id()
        if sid is None:
            return
        self._mode = "goal"
        self._target_id = sid
        sp = self.app.db.get_sprint(sid)
        inp = self.query_one("#sprint-input", Input)
        inp.placeholder = f"Goal for '{sp.name}'"
        inp.value = sp.goal or ""
        inp.focus()

    def action_filter_by(self) -> None:
        sid = self._selected_sprint_id()
        if sid is None:
            return
        sp = self.app.db.get_sprint(sid)
        if sp.project_id is not None:
            self.app.set_active_project(sp.project_id)
        self.app.set_active_sprint(sid)
        try:
            self.app.switch_screen("kanban")
        except Exception:
            pass

    def action_blur_input(self) -> None:
        self._mode = None
        self._target_id = None
        inp = self.query_one("#sprint-input", Input)
        inp.value = ""
        inp.placeholder = "(press n to add a new sprint)"
        self.query_one("#sprint-table", DataTable).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "sprint-input":
            return
        text = event.value.strip()
        if not text:
            self.action_blur_input()
            return
        if self._mode == "new":
            # Parse "name [target]" — last whitespace-separated int is target
            parts = text.split()
            target = 0
            if parts and parts[-1].isdigit():
                target = int(parts[-1])
                parts = parts[:-1]
            name = " ".join(parts) or text
            scope_pid = self.app.project_filter.scoped_project_id
            today = date.today().isoformat()
            end = (date.today() + timedelta(days=14)).isoformat()
            self.app.db.add_sprint(scope_pid, name, today, end,
                                   pomodoro_target=target)
        elif self._mode == "target" and self._target_id is not None:
            try:
                self.app.db.update_sprint(self._target_id, pomodoro_target=int(text))
            except ValueError:
                pass
        elif self._mode == "goal" and self._target_id is not None:
            self.app.db.update_sprint(self._target_id, goal=text)
        self.action_blur_input()
        self.refresh_sprints()
