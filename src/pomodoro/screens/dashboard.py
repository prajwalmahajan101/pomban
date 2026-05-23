from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static

from pomodoro.core.models import Task
from pomodoro.widgets.stats_strip import StatsStrip
from pomodoro.widgets.timer_display import TimerDisplay


class TaskItem(ListItem):
    def __init__(self, task: Task) -> None:
        mark = {"todo": "[ ]", "doing": "[~]", "done": "[x]"}[task.status]
        label = f"{mark} {task.title}"
        if task.tags:
            label += f"  [dim]#{task.tags.replace(',', ' #')}[/]"
        super().__init__(Static(label))
        self.task_data = task


class DashboardScreen(Screen):
    CSS = """
    DashboardScreen { layout: vertical; }
    #stats { dock: top; }
    #main { height: 1fr; }
    #timer-pane { width: 1fr; border: round $primary; }
    #task-pane { width: 50; border: round $secondary; }
    #task-list { height: 1fr; }
    #task-input { dock: bottom; }
    .pane-title { padding: 0 1; background: $panel; color: $text; }
    """

    BINDINGS = [
        Binding("s,space", "app.toggle", "Start/Pause"),
        Binding("r", "app.reset", "Reset"),
        Binding("shift+s,S", "app.skip", "Skip"),
        Binding("enter", "app.start_on_selected", "Start", show=False),
        Binding("n", "new_task", "New task"),
        Binding("d,x", "app.delete_task", "Delete"),
        Binding("c", "app.complete_task", "Complete"),
        Binding("1", "app.switch('dashboard')", "Dashboard"),
        Binding("2", "app.switch('kanban')", "Kanban"),
        Binding("3", "app.switch('stats')", "Stats", show=False),
        Binding("4", "app.switch('history')", "History", show=False),
        Binding("question_mark", "app.help", "Help"),
        Binding("t", "app.cycle_theme", "Theme"),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield StatsStrip(id="stats")
        with Horizontal(id="main"):
            with Vertical(id="timer-pane"):
                yield Static("[b]Timer[/]", classes="pane-title")
                yield TimerDisplay(id="timer")
            with Vertical(id="task-pane"):
                yield Static("[b]Tasks[/]", classes="pane-title")
                yield ListView(id="task-list")
                yield Input(placeholder="Add a task — use #tag inline", id="task-input")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_tasks()
        self.refresh_stats()
        self.refresh_timer()

    def refresh_timer(self) -> None:
        td = self.query_one(TimerDisplay)
        eng = self.app.engine
        td.remaining = eng.remaining
        td.phase = eng.phase
        td.running = eng.running
        td.cycles = eng.completed_focus_cycles
        td.active_task = self.app.active_task.title if self.app.active_task else ""

    def refresh_tasks(self) -> None:
        lv = self.query_one("#task-list", ListView)
        lv.clear()
        for t in self.app.db.list_tasks():
            lv.append(TaskItem(t))

    def refresh_stats(self) -> None:
        s = self.app.db.stats_today()
        strip = self.query_one(StatsStrip)
        strip.sessions = s["sessions"]
        strip.focus_seconds = s["focus_seconds"]
        strip.streak = s["streak"]

    def action_new_task(self) -> None:
        self.query_one("#task-input", Input).focus()

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
