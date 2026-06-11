"""Base class for the app's primary navigable screens.

Defines ``refresh_view()`` — the single entry point the app calls after state
changes (a task moved, a filter changed, a session ended). This replaces the
old duck-typed loop in ``app.py`` that blind-``getattr``'d a hardcoded list of
~9 refresh-method names across every screen and swallowed failures. Now each
screen declares exactly how it refreshes by overriding one typed method.
"""

from __future__ import annotations

import contextlib

from textual.screen import Screen
from textual.widgets import Header

from pomban.widgets.context_header import ContextHeader


class AppScreen(Screen):
    def compose_header(self):
        """Yield the standard top-of-screen widgets: clock Header + ContextHeader.

        Every concrete screen's ``compose`` should ``yield from
        self.compose_header()`` instead of yielding ``Header`` directly, so the
        Project · Sprint progress strip stays uniform.
        """
        yield Header(show_clock=True)
        yield ContextHeader(id="context-header")

    def _refresh_context_header(self) -> None:
        try:
            ch = self.query_one("#context-header", ContextHeader)
        except Exception:
            return
        with contextlib.suppress(Exception):
            ch.refresh_from_app(self.app)

    def refresh_view(self) -> None:
        """Re-render this screen from the current app/db state.

        Overridden by each concrete screen. Concrete overrides should call
        ``self._refresh_context_header()`` (or rely on ``super().refresh_view()``)
        so the persistent strip stays in sync with the active filter.
        """
        self._refresh_context_header()

    def refresh_timer(self) -> None:
        """Re-render only the timer-dependent parts of this screen.

        Called from the app's 0.25s tick (hot path), separate from the heavier
        ``refresh_view``. No-op by default; a screen with a live timer display
        (e.g. the dashboard) overrides it. Having it on the base means the tick
        can call it on any ``AppScreen`` without duck-typed ``hasattr`` checks.
        """

    def action_focus_pane(self, target: str) -> None:
        """Focus a named pane by its widget id (btop-style letter selection).

        Default implementation focuses the widget whose ``id`` is ``target`` if it
        exists and can take focus. Screens whose "panes" aren't focusable widgets
        (e.g. the kanban columns, which are tracked by a cursor) override this.
        """
        try:
            widget = self.query_one(f"#{target}")
        except Exception:
            return
        if getattr(widget, "can_focus", False) or getattr(widget, "can_focus_children", False):
            with contextlib.suppress(Exception):
                widget.focus()
