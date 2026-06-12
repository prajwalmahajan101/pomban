"""TodayScreen — at-a-glance summary of today's focus work.

Bound to the ``7`` nav key. Reads from existing DB helpers
(`stats_today`, `top_tasks`, `count_today_interruptions`,
`avg_interruptions_per_focus`, `sessions_per_project(since_days=1)`)
and the active filter / sprint progress so the digest mirrors what
the user has actually been doing.

Read-only screen — no actions beyond navigation.
"""

from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Static

from pomban.screens.base import AppScreen


def _fmt_minutes(seconds: int) -> str:
    minutes = max(0, seconds) // 60
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if h else f"{m}m"


class TodayScreen(AppScreen):
    CSS = """
    TodayScreen { layout: vertical; }
    TodayScreen #today-scroll { padding: 0 2; }
    TodayScreen .panel { margin-bottom: 1; padding: 0 1; }
    TodayScreen .panel-title { color: $primary; text-style: bold; }
    """

    BINDINGS = [
        Binding("1", "app.switch('dashboard')", "Dashboard"),
        Binding("2", "app.switch('kanban')", "Kanban"),
        Binding("3", "app.switch('stats')", "Stats"),
        Binding("4", "app.switch('history')", "History"),
        Binding("5", "app.switch('projects')", "Projects", show=False),
        Binding("6", "app.switch('sprints')", "Sprints", show=False),
        Binding("7", "app.switch('today')", "Today"),
        Binding("question_mark", "app.help", "Help"),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield from self.compose_header()
        with VerticalScroll(id="today-scroll"):
            yield Static("", id="today-context", classes="panel")
            yield Static("", id="today-sessions", classes="panel")
            yield Static("", id="today-top-tasks", classes="panel")
            yield Static("", id="today-interruptions", classes="panel")
            yield Static("", id="today-by-project", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_view()

    def refresh_view(self) -> None:
        super().refresh_view()
        db = self.app.db
        self._refresh_context()
        self._refresh_sessions(db)
        self._refresh_top_tasks(db)
        self._refresh_interruptions(db)
        self._refresh_by_project(db)

    # ---------- panels ----------
    def _refresh_context(self) -> None:
        proj = self.app.active_project_label() or "All"
        sprint_payload = self.app._facade.active_sprint_progress()
        lines = ["[panel-title]Today[/]", "", f"Project: [b]{escape(proj)}[/]"]
        if sprint_payload is not None:
            sp = sprint_payload["sprint"]
            target = sprint_payload["target"]
            completed = sprint_payload["completed"]
            days_left = sprint_payload["days_left"]
            if target:
                lines.append(
                    f"Sprint:  [b]{escape(sp.name)}[/]  {completed}/{target} 🍅  ·  "
                    f"{days_left}d left"
                )
            else:
                lines.append(
                    f"Sprint:  [b]{escape(sp.name)}[/]  {completed} 🍅  ·  {days_left}d left"
                )
        else:
            lines.append("Sprint:  —")
        self.query_one("#today-context", Static).update("\n".join(lines))

    def _refresh_sessions(self, db) -> None:
        s = db.stats_today()
        body = (
            "[panel-title]Sessions[/]\n\n"
            f"Completed focus:  [b]{s['sessions']}[/]\n"
            f"Focus time:       [b]{_fmt_minutes(s['focus_seconds'])}[/]\n"
            f"Streak:           [b]{s['streak']}[/] day(s)"
        )
        self.query_one("#today-sessions", Static).update(body)

    def _refresh_top_tasks(self, db) -> None:
        top = db.top_tasks(limit=5)
        if not top:
            body = "[panel-title]Top tasks[/]\n\n[dim]No focus sessions yet.[/]"
        else:
            rows = "\n".join(
                f"  · {escape(title)}  [dim]({_fmt_minutes(mins * 60)})[/]" for title, mins in top
            )
            body = f"[panel-title]Top tasks[/]\n\n{rows}"
        self.query_one("#today-top-tasks", Static).update(body)

    def _refresh_interruptions(self, db) -> None:
        today_n = db.count_today_interruptions()
        avg = db.avg_interruptions_per_focus()
        body = (
            "[panel-title]Interruptions[/]\n\n"
            f"Today:                [b]{today_n}[/]\n"
            f"Avg / completed focus: [b]{avg:.1f}[/]"
        )
        self.query_one("#today-interruptions", Static).update(body)

    def _refresh_by_project(self, db) -> None:
        rows = db.sessions_per_project(since_days=1)
        if not rows:
            body = "[panel-title]By project (today)[/]\n\n[dim]No focus sessions today.[/]"
        else:
            entries = "\n".join(
                f"  [reverse {color}] {escape(name)} [/]  {sessions} 🍅  "
                f"[dim]({_fmt_minutes(secs)})[/]"
                for name, color, sessions, secs in rows
            )
            body = f"[panel-title]By project (today)[/]\n\n{entries}"
        self.query_one("#today-by-project", Static).update(body)
