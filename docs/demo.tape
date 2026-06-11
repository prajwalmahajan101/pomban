# pomodoro — animated README hero.
#
# Render with: vhs docs/demo.tape
# Output:      docs/screenshots/demo.gif
#
# Requires vhs (https://github.com/charmbracelet/vhs), ffmpeg, and
# ttyd on $PATH. Assumes `pomodoro` is on PATH (pipx install or
# uv tool install).

Output docs/screenshots/demo.gif

Set FontSize 16
Set Width 1400
Set Height 900
Set Padding 20
Set Theme "Catppuccin Mocha"

Type "pomodoro"
Enter
Sleep 2s

# Add a task with the inline syntax.
Type "n"
Sleep 500ms
Type "Wire OAuth flow @release ~3 #backend"
Enter
Sleep 1s

# Start the focus session.
Type "s"
Sleep 3s

# Switch to the kanban board.
Type "2"
Sleep 2s

# Add a kanban card.
Type "n"
Sleep 500ms
Type "Review release notes"
Enter
Sleep 1s

# Open the card-detail view.
Type "i"
Sleep 2s
Escape
Sleep 500ms

# Move to stats.
Type "3"
Sleep 2s

# Cycle theme.
Type "t"
Sleep 1s
Type "t"
Sleep 1s

# Open the help overlay.
Type "?"
Sleep 2s
Escape
Sleep 500ms

# Quit.
Type "q"
Sleep 1s
