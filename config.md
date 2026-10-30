## Configuration Options

- **timer_duration_seconds**: How long the front countdown timer runs before automatically revealing the answer (default: `30`)
- **auto_show_answer**: Whether to automatically reveal the answer when front countdown expires (default: `true`)
- **show_pause_indicator**: Show the pause icon prefix when the timer is paused (default: `true`)
- **auto_grade_ease**: What grade to apply when the back countdown expires. Values: `0` (off, show answer only), `1` (Again = fail, default), `2` (Hard), `3` (Good = pass), `4` (Easy)
- **auto_grade_grace_seconds**: Dedicated reading countdown duration (seconds) on the answer screen before auto-grading fires. Resets cleanly whenever the answer appears (default: `30`)
