"""Regression: user text with markup metacharacters must not break Rich
markup rendering. A title containing an unbalanced closing tag like '[/]' used to
raise MarkupError and crash the board/list/timer render."""

from textual.content import Content

from pomban.core.models import Task
from pomban.widgets.card import (
    TaskCard,
    render_chips,
    render_project_badge,
    render_sprint_chip,
)

NASTY = "boom [/] [b]unclosed [red]x"


def _parses(markup: str) -> bool:
    Content.from_markup(markup)  # raises MarkupError on bad markup
    return True


def test_render_helpers_escape_user_text():
    assert _parses(render_project_badge(NASTY, "cyan"))
    assert _parses(render_project_badge("ev[/]il", None))
    assert _parses(render_chips("a[/]b,[red]c,normal"))
    assert _parses(render_sprint_chip(NASTY))


def test_task_card_body_is_valid_markup(monkeypatch):
    # Capture the markup string the card hands to Static.update and verify IT parses
    # (the rendered output legitimately contains literal '[/]', so re-parsing that
    # would be meaningless — we must check the pre-render markup).
    captured: list[str] = []
    monkeypatch.setattr(TaskCard, "update", lambda self, content="", **k: captured.append(content))
    t = Task(id=1, title=NASTY, status="todo", tags="x[/]y,z", estimated_pomodoros=2, position=0)
    TaskCard(
        t, project_name="p[/]roj", project_color="cyan", sprint_name="s[/]print", actual_pomodoros=1
    )
    assert captured, "TaskCard.update was not called"
    assert _parses(captured[-1])
