"""Pure parser for the inline task-entry mini-syntax.

Splits free text into a title plus optional metadata tokens:
  ``#tag``     → a tag (repeatable)
  ``@project`` → project name (first wins; later ``@`` tokens become title words)
  ``!sprint``  → sprint name (first wins)
  ``~N``       → pomban estimate (first valid wins; a bad ``~N`` stays a title word)

No I/O: the app layer resolves project/sprint names to ids and applies the
active-filter defaults. Unit-testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedTask:
    title: str
    tags: list[str] = field(default_factory=list)
    project_name: str | None = None
    sprint_name: str | None = None
    estimate: int = 0

    @property
    def tags_csv(self) -> str:
        return ",".join(self.tags)


def parse_task_input(text: str) -> ParsedTask:
    title_words: list[str] = []
    tags: list[str] = []
    project_name: str | None = None
    sprint_name: str | None = None
    estimate = 0
    for w in text.split():
        if w.startswith("#") and len(w) > 1:
            tags.append(w[1:])
        elif w.startswith("@") and len(w) > 1 and project_name is None:
            project_name = w[1:]
        elif w.startswith("!") and len(w) > 1 and sprint_name is None:
            sprint_name = w[1:]
        elif w.startswith("~") and len(w) > 1 and estimate == 0:
            try:
                estimate = int(w[1:])
            except ValueError:
                title_words.append(w)
        else:
            title_words.append(w)
    title = " ".join(title_words) or text
    return ParsedTask(
        title=title,
        tags=tags,
        project_name=project_name,
        sprint_name=sprint_name,
        estimate=estimate,
    )
