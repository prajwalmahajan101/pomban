from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from pomodoro.widgets.heatmap import Heatmap


def _fmt_hours(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if h else f"{m}m"


class StatsScreen(Screen):
    CSS = """
    StatsScreen { layout: vertical; }
    .section { padding: 1 2; }
    .section-title { text-style: bold; color: $accent; }
    """

    BINDINGS = [
        Binding("1", "app.switch('dashboard')", "Dashboard"),
        Binding("2", "app.switch('kanban')", "Kanban"),
        Binding("3", "app.switch('stats')", "Stats"),
        Binding("4", "app.switch('history')", "History"),
        Binding("question_mark", "app.help", "Help"),
        Binding("t", "app.cycle_theme", "Theme"),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll():
            with Vertical(classes="section"):
                yield Static("[b]Last 7 days[/]", classes="section-title")
                yield Heatmap(id="heatmap-7")
            with Vertical(classes="section"):
                yield Static("[b]Last 30 days[/]", classes="section-title")
                yield Heatmap(id="heatmap-30")
            with Vertical(classes="section"):
                yield Static("[b]Top tasks[/]", classes="section-title")
                yield Static(id="top-tasks")
            with Vertical(classes="section"):
                yield Static("[b]Summary[/]", classes="section-title")
                yield Static(id="summary")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_stats_screen()

    def refresh_stats_screen(self) -> None:
        db = self.app.db
        seven = db.daily_focus_minutes(7)
        thirty = db.daily_focus_minutes(30)
        self.query_one("#heatmap-7", Heatmap).set_data(seven)
        self.query_one("#heatmap-30", Heatmap).set_data(thirty)
        top = db.top_tasks(5)
        if top:
            top_text = "\n".join(f"  {i+1}. {title} — {_fmt_hours(m)}" for i, (title, m) in enumerate(top))
        else:
            top_text = "[dim]no completed focus sessions yet[/]"
        self.query_one("#top-tasks", Static).update(top_text)
        today = db.stats_today()
        avg = db.avg_interruptions_per_focus()
        total_mins = sum(m for _, m in thirty)
        summary = (
            f"  Today: {today['sessions']} sessions, {_fmt_hours(today['focus_seconds']//60)}\n"
            f"  Streak: {today['streak']} day(s)\n"
            f"  30-day total: {_fmt_hours(total_mins)}\n"
            f"  Avg interruptions / focus session: {avg:.1f}"
        )
        self.query_one("#summary", Static).update(summary)
