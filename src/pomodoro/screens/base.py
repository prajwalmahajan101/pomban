"""Base class for the app's primary navigable screens.

Defines ``refresh_view()`` — the single entry point the app calls after state
changes (a task moved, a filter changed, a session ended). This replaces the
old duck-typed loop in ``app.py`` that blind-``getattr``'d a hardcoded list of
~9 refresh-method names across every screen and swallowed failures. Now each
screen declares exactly how it refreshes by overriding one typed method.
"""
from __future__ import annotations

from textual.screen import Screen


class AppScreen(Screen):
    def refresh_view(self) -> None:
        """Re-render this screen from the current app/db state.

        Overridden by each concrete screen. The base is a no-op so a screen that
        needs no refresh (or hasn't been mounted yet) is safe to call.
        """
