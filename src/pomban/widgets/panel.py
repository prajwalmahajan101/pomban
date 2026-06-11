"""btop-style panel titles: a title label with one highlighted hotkey letter.

Each navigable pane shows its title with a single letter emphasized; pressing
that letter focuses the pane (see ``AppScreen.action_focus_pane``). The emphasis
uses an accent color when available and always underlines, so the hint survives
NO_COLOR / low-color terminals (underline is a style, not a color).
"""

from __future__ import annotations

from rich.markup import escape

from pomban.core.colors import adapt

# Fixed, readable accent for the hotkey letter. We can't reference the Textual
# theme's ``$accent`` from inside a Rich markup string, so use a stable bright
# color that ``adapt`` degrades for low-color / NO_COLOR terminals.
HOTKEY_COLOR = "bright_cyan"


def panel_title(label: str, hotkey: str | None = None) -> str:
    """Return Rich markup for a bold panel title with ``hotkey`` highlighted.

    The first case-insensitive occurrence of ``hotkey`` in ``label`` is underlined
    and accent-colored so it reads as a selectable shortcut. If the hotkey is None
    or not present in the label, the label is simply bolded. All text is escaped.
    """
    if not hotkey:
        return f"[b]{escape(label)}[/]"
    idx = label.lower().find(hotkey.lower())
    if idx < 0:
        return f"[b]{escape(label)}[/]"
    before, ch, after = label[:idx], label[idx], label[idx + 1 :]
    c = adapt(HOTKEY_COLOR)
    mark = f"[{c} u]{escape(ch)}[/]" if c else f"[u]{escape(ch)}[/]"
    return f"[b]{escape(before)}{mark}{escape(after)}[/]"
