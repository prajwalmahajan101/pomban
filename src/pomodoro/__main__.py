import sys

from pomodoro.app import PomodoroApp


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "export":
        from pomodoro.core.db import DB
        from pomodoro.core.exporter import export_markdown
        days = 7
        for i, arg in enumerate(args):
            if arg == "--since" and i + 1 < len(args):
                v = args[i + 1].rstrip("d")
                try:
                    days = int(v)
                except ValueError:
                    pass
        db = DB()
        sys.stdout.write(export_markdown(db, days=days))
        sys.stdout.write("\n")
        db.close()
        return
    PomodoroApp().run()


if __name__ == "__main__":
    main()
