from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from pomodoro.screens.base import AppScreen
from textual.widgets import Footer, Header, Static

from pomodoro.widgets.bar_chart import BarChart, VerticalBarChart
from pomodoro.widgets.heatmap import Heatmap
from pomodoro.widgets.sparkline import Sparkline


def _fmt_hours(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if h else f"{m}m"


_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class StatsScreen(AppScreen):
    CSS = """
    StatsScreen { layout: vertical; }
    .section { padding: 1 2; }
    .section-title { text-style: bold; color: $accent; }
    """

    BINDINGS = [
        Binding("d", "set_view('day')", "Daily", show=True),
        Binding("w", "set_view('week')", "Weekly", show=True),
        Binding("m", "set_view('month')", "Monthly", show=True),
        Binding("1", "app.switch('dashboard')", "Dashboard"),
        Binding("2", "app.switch('kanban')", "Kanban"),
        Binding("3", "app.switch('stats')", "Stats"),
        Binding("4", "app.switch('history')", "History"),
        Binding("5", "app.switch('projects')", "Projects", show=False),
        Binding("6", "app.switch('sprints')", "Sprints", show=False),
        Binding("7", "app.switch('music')", "Music", show=False),
        Binding("question_mark", "app.help", "Help"),
        Binding("t", "app.cycle_theme", "Theme"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.granularity = "day"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll():
            with Vertical(classes="section"):
                yield Static("[b]View: daily[/]  [dim](d/w/m to switch)[/]", id="view-title", classes="section-title")
                yield Static("", id="filter-label")
            with Vertical(classes="section"):
                yield Static("[b]Focus minutes per bucket[/]", classes="section-title")
                yield VerticalBarChart(id="bucket-bars")
            with Vertical(classes="section"):
                yield Static("[b]Estimate accuracy trend (1.0 = on target)[/]", classes="section-title")
                yield Sparkline(id="est-spark")
                yield Static("", id="est-detail")
            with Vertical(classes="section"):
                yield Static("[b]Last 30 days heatmap[/]", classes="section-title")
                yield Heatmap(id="heatmap-30")
            with Vertical(classes="section"):
                yield Static("[b]By project (last 30 days)[/]", classes="section-title")
                yield BarChart(id="by-project")
            with Vertical(classes="section"):
                yield Static("[b]Project drill-down[/]", classes="section-title")
                yield Static(id="project-drill")
            with Vertical(classes="section"):
                yield Static("[b]Sprint burndown[/]", classes="section-title")
                yield Sparkline(id="burndown-spark")
                yield Static(id="burndown-detail")
            with Vertical(classes="section"):
                yield Static("[b]Top tasks[/]", classes="section-title")
                yield Static(id="top-tasks")
            with Vertical(classes="section"):
                yield Static("[b]Summary[/]", classes="section-title")
                yield Static(id="summary")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_stats_screen()

    def action_set_view(self, view: str) -> None:
        if view in ("day", "week", "month"):
            self.granularity = view
            self.refresh_stats_screen()

    def refresh_view(self) -> None:
        self.refresh_stats_screen()

    def refresh_stats_screen(self) -> None:
        db = self.app.db
        # Project filter
        active_pid = self.app.project_filter.scoped_project_id
        active_label = self.app.active_project_label()
        # Title
        view_word = {"day": "daily", "week": "weekly", "month": "monthly"}[self.granularity]
        self.query_one("#view-title", Static).update(
            f"[b]View: {view_word}[/]  [dim](d/w/m to switch)[/]"
        )
        if active_label:
            color = self.app.active_project_color()
            self.query_one("#filter-label", Static).update(
                f"  [reverse {color}] {escape(active_label)} [/]  [dim](press P to change filter)[/]"
            )
        else:
            self.query_one("#filter-label", Static).update("  [dim]all projects (press P to filter)[/]")
        # Bucket chart
        n_buckets = {"day": 14, "week": 12, "month": 12}[self.granularity]
        buckets = db.sessions_by_bucket(self.granularity, n_buckets=n_buckets,
                                        project_id=active_pid)
        bar_data = [(b[0], b[1]) for b in buckets]
        bar_color = self.app.active_project_color() if active_pid else "cyan"
        self.query_one("#bucket-bars", VerticalBarChart).set_data(bar_data, height=6, color=bar_color)
        # Estimate sparkline
        ratios = [b[2] for b in buckets]
        self.query_one("#est-spark", Sparkline).set_values(ratios, color="green")
        avg_ratio = sum(r for r in ratios if r > 0) / max(1, sum(1 for r in ratios if r > 0))
        if avg_ratio > 0:
            if avg_ratio < 0.9:
                est_text = f"  avg ratio = {avg_ratio:.2f} — your estimates are [red]{(1/avg_ratio):.1f}× too optimistic[/]"
            elif avg_ratio > 1.1:
                est_text = f"  avg ratio = {avg_ratio:.2f} — your estimates are [yellow]{avg_ratio:.1f}× too pessimistic[/]"
            else:
                est_text = f"  avg ratio = [green]{avg_ratio:.2f}[/] — on target"
        else:
            est_text = "  [dim]no estimates set yet — add ~N when creating a task[/]"
        self.query_one("#est-detail", Static).update(est_text)
        # 30-day heatmap (respects project filter)
        thirty = db.daily_focus_minutes(30, project_id=active_pid)
        self.query_one("#heatmap-30", Heatmap).set_data(thirty)
        # By-project (replaces or supplements depending on filter)
        per_proj = db.sessions_per_project(30)
        if per_proj and not active_pid:
            bar_data = [(name, secs // 60) for (name, _color, _n, secs) in per_proj]
            colors = [color for (_n2, color, _, _) in per_proj]
            self.query_one("#by-project", BarChart).set_data(
                bar_data, width=30, colors=colors, value_suffix="m"
            )
        elif active_pid:
            self.query_one("#by-project", BarChart).update("[dim]filtered to single project — see drill-down below[/]")
        else:
            self.query_one("#by-project", BarChart).update("[dim]no completed sessions yet[/]")
        # Project drill-down
        if active_pid:
            an = db.project_analytics(active_pid)
            dow_data = list(zip(_DOW, an["dow_minutes"]))
            ratio_str = (f"{an['estimate_ratio']:.2f}"
                         if an["estimate_ratio"] > 0 else "—")
            idle_warn = ""
            if an["last_session"]:
                from datetime import date as _date
                try:
                    last = _date.fromisoformat(an["last_session"])
                    delta = (_date.today() - last).days
                    if delta >= 7:
                        idle_warn = f"\n  [yellow]⚠ no sessions in {delta} days[/]"
                except Exception:
                    pass
            drill = (
                f"  Total:        {_fmt_hours(an['total_minutes'])}  ({an['active_days']} active days)\n"
                f"  This month:   {_fmt_hours(an['month_minutes'])}\n"
                f"  This week:    {_fmt_hours(an['week_minutes'])}\n"
                f"  Avg per day:  {_fmt_hours(an['avg_per_active_day_minutes'])}\n"
                f"  Estimate ratio: {ratio_str}  "
                f"({an['actual_pomodoros']} 🍅 actual / {an['estimated_pomodoros']} estimated)\n"
                f"  Day-of-week minutes: " +
                "  ".join(f"{d} {m}" for d, m in dow_data) +
                idle_warn
            )
            self.query_one("#project-drill", Static).update(drill)
        else:
            self.query_one("#project-drill", Static).update(
                "[dim]filter to a project (press P) to see drill-down stats[/]"
            )
        # Burndown
        sprint_id = self.app.active_sprint_id
        if sprint_id is not None:
            try:
                sp = db.get_sprint(sprint_id)
                bd = db.sprint_burndown(sprint_id)
                self.query_one("#burndown-spark", Sparkline).set_values(
                    [float(x) for x in bd["remaining_series"]], color="bright_yellow"
                )
                pace = bd["pace"]
                pace_str = (f"[green]+{pace} 🍅 ahead[/]" if pace > 0
                            else f"[red]{pace} 🍅 behind[/]" if pace < 0
                            else "[dim]on pace[/]")
                detail = (
                    f"  Sprint: [b]{sp.name}[/] · {sp.start_date} → {sp.end_date}\n"
                    f"  Target: {bd['target']} 🍅 · Done: {bd['completed']} · "
                    f"Days left: {bd['days_left']} · {pace_str}"
                )
                self.query_one("#burndown-detail", Static).update(detail)
            except Exception as e:
                self.query_one("#burndown-detail", Static).update(f"[red]burndown error: {e}[/]")
        else:
            self.query_one("#burndown-spark", Sparkline).set_values([])
            self.query_one("#burndown-detail", Static).update(
                "[dim]no active sprint filter — press F to pick a sprint, or 6 to manage them[/]"
            )
        # Top tasks
        top = db.top_tasks(5)
        if top:
            top_text = "\n".join(f"  {i+1}. {title} — {_fmt_hours(m)}" for i, (title, m) in enumerate(top))
        else:
            top_text = "[dim]no completed focus sessions yet[/]"
        self.query_one("#top-tasks", Static).update(top_text)
        # Summary
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
