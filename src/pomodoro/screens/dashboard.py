from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static

from pomodoro.core.models import Task
from pomodoro.screens.base import AppScreen
from pomodoro.widgets.stats_strip import StatsStrip
from pomodoro.widgets.timer_display import TimerDisplay
from pomodoro.widgets.card import render_project_badge
from pomodoro.widgets.panel import panel_title


class TaskItem(ListItem):
    def __init__(self, task: Task, project_name: str | None = None,
                 project_color: str | None = None) -> None:
        mark = {"todo": "[ ]", "doing": "[~]", "done": "[x]"}[task.status]
        badge = render_project_badge(project_name, project_color)
        label = f"{badge} {mark} {escape(task.title)}"
        if task.tags:
            tags = escape(task.tags.replace(",", " #"))
            label += f"  [dim]#{tags}[/]"
        if task.estimated_pomodoros:
            label += f"  [dim]🍅×{task.estimated_pomodoros}[/]"
        super().__init__(Static(label))
        self.task_data = task


class DashboardScreen(AppScreen):
    CSS = """
    DashboardScreen { layout: vertical; }
    #stats { dock: top; }
    #main { height: 1fr; }
    /* All panes share a dim base border so only the focused one stands out. */
    #timer-pane { width: 1fr; border: round $primary-darken-2; }
    #task-pane { width: 50; border: round $primary-darken-2; }
    /* Active-panel highlight (btop-style): accent border + accent title bar. */
    #timer-pane:focus, #task-pane:focus-within {
        border: round $accent;
    }
    #timer-pane:focus .pane-title,
    #task-pane:focus-within .pane-title {
        background: $accent;
        color: $text;
        text-style: bold;
    }
    #task-list { height: 1fr; }
    #task-input { dock: bottom; }
    .pane-title { padding: 0 1; background: $panel; color: $text; }
    /* Responsive: stack Timer above Tasks on a narrow terminal. */
    DashboardScreen.-narrow #main { layout: vertical; }
    DashboardScreen.-narrow #timer-pane { width: 1fr; height: auto; }
    DashboardScreen.-narrow #task-pane { width: 1fr; height: 1fr; }
    """

    BINDINGS = [
        Binding("s,space", "app.toggle", "Start/Pause"),
        # Tab/Shift+Tab cycle focus between panels (default Textual focus movement);
        # the active-task chip cycle moves to backtick to free Tab.
        Binding("grave_accent", "cycle_active_chip", "Cycle task", show=False),
        # btop-style pane selection: press the highlighted letter in a pane title.
        Binding("i", "focus_pane('timer-pane')", "Timer pane", show=False),
        Binding("a", "focus_pane('task-list')", "Tasks pane", show=False),
        Binding("r", "app.reset", "Reset"),
        Binding("shift+s,S", "app.skip", "Skip"),
        Binding("enter", "app.start_on_selected", "Start", show=False),
        Binding("n", "new_task", "New task"),
        Binding("d,x", "app.delete_task", "Delete"),
        Binding("c", "app.complete_task", "Complete"),
        Binding("e", "app.edit_task", "Edit"),
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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield StatsStrip(id="stats")
        with Horizontal(id="main"):
            with Vertical(id="timer-pane"):
                yield Static(panel_title("Timer", "i"), classes="pane-title")
                yield TimerDisplay(id="timer")
            with Vertical(id="task-pane"):
                yield Static(panel_title("Tasks", "a"), classes="pane-title")
                yield ListView(id="task-list")
                yield Input(placeholder="Add a task — use #tag inline", id="task-input")
        yield Footer()

    def on_mount(self) -> None:
        # Make the timer pane focusable so it can be the active panel (it has no
        # focusable children); task pane highlights via :focus-within.
        self.query_one("#timer-pane").can_focus = True
        self.refresh_view()
        self.query_one("#task-list", ListView).focus()

    def refresh_view(self) -> None:
        self.refresh_tasks()
        self.refresh_stats()
        self.refresh_timer()
        self._update_subtitle()

    def refresh_timer(self) -> None:
        td = self.query_one(TimerDisplay)
        eng = self.app.engine
        td.remaining = eng.remaining
        td.phase = eng.phase
        td.running = eng.running
        td.cycles = eng.completed_focus_cycles
        td.active_task = self.app.active_task.title if self.app.active_task else ""
        td.active_tasks = [t.title for t in self.app.active_tasks]
        td.active_index = self.app.active_chip_index

    def refresh_tasks(self) -> None:
        lv = self.query_one("#task-list", ListView)
        lv.clear()
        pf = self.app.project_filter_for_db()
        tasks = self.app.db.list_tasks(project_filter=pf)
        if self.app.active_sprint_id is not None:
            tasks = [t for t in tasks if t.sprint_id == self.app.active_sprint_id]
        # Project resolution cache
        proj_cache: dict[int, tuple[str, str]] = {}
        for t in tasks:
            pname = pcolor = None
            if t.project_id is not None:
                if t.project_id not in proj_cache:
                    try:
                        p = self.app.db.get_project(t.project_id)
                        proj_cache[t.project_id] = (p.name, p.color)
                    except Exception:
                        proj_cache[t.project_id] = ("?", "white")
                pname, pcolor = proj_cache[t.project_id]
            lv.append(TaskItem(t, project_name=pname, project_color=pcolor))

    def _update_subtitle(self) -> None:
        label = self.app.active_project_label() or ""
        if self.app.active_sprint_id is not None:
            try:
                label = f"{label}  ▸ {self.app.db.get_sprint(self.app.active_sprint_id).name}"
            except Exception:
                pass
        try:
            self.sub_title = label.strip()
        except Exception:
            pass

    def refresh_stats(self) -> None:
        s = self.app.db.stats_today()
        strip = self.query_one(StatsStrip)
        strip.sessions = s["sessions"]
        strip.focus_seconds = s["focus_seconds"]
        strip.streak = s["streak"]

    def action_new_task(self) -> None:
        self.query_one("#task-input", Input).focus()

    def action_cycle_active_chip(self) -> None:
        """Cosmetic: highlight the next active-task chip. Never touches the engine."""
        n = len(self.app.active_tasks)
        if n <= 1:
            return
        self.app.active_chip_index = (self.app.active_chip_index + 1) % n
        self.refresh_timer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, TaskItem):
            self.app.start_focus_on(event.item.task_data)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "task-input":
            return
        title = event.value.strip()
        if not title:
            return
        self.app.add_task_from_input(title)
        event.input.value = ""
        self.query_one("#task-list", ListView).focus()

    def selected_task(self) -> Task | None:
        lv = self.query_one("#task-list", ListView)
        if lv.index is None:
            return None
        child = lv.children[lv.index]
        return child.task_data if isinstance(child, TaskItem) else None
