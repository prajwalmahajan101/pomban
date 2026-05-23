# Example plugin: print-events

A minimal Pomodoro plugin that prints each phase transition to stderr.

## Install

```bash
pip install -e ./examples/plugin-print-events
```

The plugin registers via entry point `pomodoro.hooks` and is auto-discovered when the app starts.

## Hooks supported

- `on_phase_started(phase, task_title)`
- `on_phase_completed(phase, task_title, completed)`

Errors raised inside any hook are caught and logged to `~/.local/state/pomodoro/plugins.log` — they will never crash the app.
