# Code Review — Current State

Stack: tui
_Last reviewed: 2026-05-25_

## Maturity
**Level 50 — Growing System**

Solid, well-separated fundamentals (pure timer engine, clean SQLite layer with real migrations, isolated side-effect modules). Feature surface has grown fast — projects, sprints, multi-task focus, music, plugins — and the orchestration layer (`app.py`) is now carrying that growth as a god object. Scaling concerns are emerging in the event loop and refresh plumbing.

## Current Scorecard (Weighted)

| Category | Weight | Score | Weighted |
|---|---|---|---|
| Event Loop & Input Handling | 2.0 | 6 | 12.0 |
| Screen State & View Composition | 1.8 | 5 | 9.0 |
| Keyboard Navigation & Shortcut Discoverability | 1.8 | 6 | 10.8 |
| Render Performance & Redraw Strategy | 1.6 | 6 | 9.6 |
| Terminal Compatibility (truecolor, sixel, fallbacks) | 1.5 | 5 | 7.5 |
| Resize & Layout Responsiveness | 1.5 | 7 | 10.5 |
| Error Handling & Crash Recovery (restore terminal state) | 1.5 | 6 | 9.0 |
| Concurrency & Cancellation | 1.5 | 6 | 9.0 |
| Accessibility (screen reader, no-color, motion) | 1.3 | 4 | 5.2 |
| Theming & Color Architecture | 1.3 | 6 | 7.8 |
| Configuration & Environment Management | 1.2 | 7 | 8.4 |
| Logging Without Corrupting the UI | 1.2 | 6 | 7.2 |
| Extensibility & Plugin Surface | 1.2 | 7 | 8.4 |
| External Process / I/O Boundaries | 1.2 | 6 | 7.2 |
| Documentation & Readability | 1.0 | 7 | 7.0 |
| Naming Quality | 1.0 | 8 | 8.0 |

Sum of weights = 22.6 · Sum of weighted = 146.6

**Overall: 6.49**

## Recent Top-Line Scores (for trend)
| Date | Maturity | Overall |
|---|---|---|
| 2026-05-25 | 50 | 6.49 |   ← current (first review)
</content>
