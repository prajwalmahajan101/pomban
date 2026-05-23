"""Minimal example plugin: prints phase events to stderr."""
import sys


def on_phase_started(phase, task_title):
    print(f"[plugin] started {phase} on {task_title!r}", file=sys.stderr)


def on_phase_completed(phase, task_title, completed):
    state = "done" if completed else "interrupted"
    print(f"[plugin] {state} {phase} on {task_title!r}", file=sys.stderr)


# The entry point points at this module-level callable container.
class plugin:
    on_phase_started = staticmethod(on_phase_started)
    on_phase_completed = staticmethod(on_phase_completed)
