import contextlib
import sys

from pomodoro.app import PomodoroApp


def _sprint_export(args: list[str]) -> None:
    """pomban sprint export <sprint_id> — prints markdown report to stdout."""
    from pomodoro.core.db import DB

    if not args:
        sys.stderr.write("usage: pomban sprint export <sprint_id>\n")
        sys.exit(2)
    try:
        sid = int(args[0])
    except ValueError:
        sys.stderr.write(f"invalid sprint id: {args[0]}\n")
        sys.exit(2)
    db = DB()
    try:
        sp = db.get_sprint(sid)
    except Exception:
        sys.stderr.write(f"sprint {sid} not found\n")
        db.close()
        sys.exit(1)
    bd = db.sprint_burndown(sid)
    proj = db.get_project(sp.project_id) if sp.project_id else None
    pname = proj.name if proj else "Inbox"
    tasks = db.list_tasks(sprint_id=sid, include_done=True)
    done = [t for t in tasks if t.status == "done"]
    not_done = [t for t in tasks if t.status != "done"]
    out = []
    out.append(f"# Sprint report: {sp.name}")
    out.append("")
    out.append(f"- **Project**: {pname}")
    out.append(f"- **Dates**: {sp.start_date} → {sp.end_date}")
    out.append(f"- **Status**: {sp.status}")
    out.append(f"- **Goal**: {sp.goal or '_(not set)_'}")
    out.append(f"- **Target**: {sp.pomodoro_target} 🍅")
    out.append(f"- **Completed**: {bd['completed']} 🍅")
    if sp.pomodoro_target:
        pct = 100 * bd["completed"] // sp.pomodoro_target
        out.append(f"- **Progress**: {pct}%")
    out.append("")
    out.append("## Shipped")
    if done:
        for t in done:
            out.append(f"- ✓ {t.title}" + (f" `#{t.tags.replace(',', ' #')}`" if t.tags else ""))
    else:
        out.append("_nothing_")
    out.append("")
    out.append("## Not shipped")
    if not_done:
        for t in not_done:
            out.append(f"- · {t.title}" + (f" `#{t.tags.replace(',', ' #')}`" if t.tags else ""))
    else:
        out.append("_everything completed_")
    out.append("")
    if sp.retrospective:
        out.append("## Retrospective")
        out.append(sp.retrospective)
        out.append("")
    sys.stdout.write("\n".join(out) + "\n")
    db.close()


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "export":
        from pomodoro.core.db import DB
        from pomodoro.core.exporter import export_markdown

        days = 7
        for i, arg in enumerate(args):
            if arg == "--since" and i + 1 < len(args):
                v = args[i + 1].rstrip("d")
                with contextlib.suppress(ValueError):
                    days = int(v)
        db = DB()
        sys.stdout.write(export_markdown(db, days=days))
        sys.stdout.write("\n")
        db.close()
        return
    if args and args[0] == "sprint" and len(args) >= 2 and args[1] == "export":
        _sprint_export(args[2:])
        return
    if "--with-music" in args:
        _launch_music_player()
    PomodoroApp().run()


def _launch_music_player() -> None:
    """Best-effort launch of the music TUI side-by-side. cliamp-specific; silent on failure."""
    import shutil
    import subprocess

    from pomodoro.core import config as cfg_module

    cfg = cfg_module.load()
    if cfg.music.player != "cliamp":
        return
    launcher = "omarchy-launch-or-focus-tui"
    if shutil.which(launcher) is None:
        return
    with contextlib.suppress(OSError):
        subprocess.Popen([launcher, "cliamp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
