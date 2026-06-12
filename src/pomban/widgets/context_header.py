"""Persistent context header: active project + sprint progress.

Rendered above the body of every :class:`AppScreen` so the Project → Sprint
→ Task hierarchy is always visible. Reads from the app: filter state,
``db.get_sprint`` and ``db.sprint_progress``. Defensive against a stale
``active_sprint_id`` (deleted under us), ``target == 0``, and malformed
sprint dates — the underlying helpers already degrade gracefully.
"""

from __future__ import annotations

from rich.markup import escape
from textual.widgets import Static

BAR_CELLS = 12


def _bar(pct: int) -> str:
    pct = max(0, min(100, int(pct)))
    filled = round(BAR_CELLS * pct / 100)
    return "▮" * filled + "▯" * (BAR_CELLS - filled)


class ContextHeader(Static):
    DEFAULT_CSS = """
    ContextHeader {
        dock: top;
        height: 1;
        padding: 0 1;
        background: $panel;
        color: $text;
    }
    """

    def refresh_from_app(self, app) -> None:
        proj_label = app.active_project_label() or "All"
        proj_color = app.active_project_color() or "white"
        proj_segment = f"Project: [reverse {proj_color}] {escape(proj_label)} [/]"
        warn_segment = self._warn_segment(app)

        sprint_id = app.active_sprint_id
        if sprint_id is None:
            hint = "(⇧P / ⇧F)" if proj_label == "All" else "(⇧F to pick)"
            self.update(f"{proj_segment}  ·  Sprint: —   {hint}{warn_segment}")
            return

        try:
            sp = app.db.get_sprint(sprint_id)
            prog = app.db.sprint_progress(sprint_id)
        except Exception:
            # Stale active_sprint_id — the underlying row may have been deleted.
            self.update(f"{proj_segment}  ·  Sprint: —   (⇧F to pick){warn_segment}")
            return

        name = escape(sp.name)
        target = prog["target"]
        completed = prog["completed"]
        days_left = prog["days_left"]
        days_str = f"{days_left} day{'s' if days_left != 1 else ''} left"
        if target <= 0:
            self.update(
                f"{proj_segment}  ·  Sprint: [b]{name}[/]  no target set   "
                f"{days_str}   (⇧F){warn_segment}"
            )
            return
        bar = _bar(prog["pct"])
        self.update(
            f"{proj_segment}  ·  Sprint: [b]{name}[/]  {completed}/{target} "
            f"{bar}  {days_str}   (⇧P / ⇧F){warn_segment}"
        )

    @staticmethod
    def _warn_segment(app) -> str:
        parts: list[str] = []
        try:
            n = app.db.count_today_interruptions()
        except Exception:
            n = 0
        if n > 0:
            parts.append(f"[yellow]⚠ {n} today[/]")
        # `· quiet` chip when desktop notifications are gated by working_hours.
        try:
            from pomban.notifications import within_working_hours

            if not within_working_hours(app.notify_cfg):
                parts.append("[dim]· quiet[/]")
        except Exception:
            pass
        if not parts:
            return ""
        return "  ·  " + "  ".join(parts)
