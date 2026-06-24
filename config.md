## Configuration Options

- **timer_duration_seconds**: How long the countdown timer runs before the card is auto-graded (default: `30`)
- **auto_show_answer**: Whether to automatically reveal the answer when time runs out (default: `true`). When `auto_grade_ease` is set, this is forced on.
- **show_pause_indicator**: Show the pause icon prefix when the timer is paused (default: `true`)
- **auto_grade_ease**: What grade to apply when the timer expires. Values: `0` (off, show answer only), `1` (Again = fail), `2` (Hard), `3` (Good = pass, default), `4` (Easy)
- **auto_grade_grace_seconds**: Delay (seconds) between the answer being shown and the auto-grade firing. Gives you a moment to read the answer first (default: `1`)
