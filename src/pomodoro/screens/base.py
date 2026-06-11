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


class AppScreen(Screen):
    def refresh_view(self) -> None:
        """Re-render this screen from the current app/db state.

        Overridden by each concrete screen. The base is a no-op so a screen that
        needs no refresh (or hasn't been mounted yet) is safe to call.
        """

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
