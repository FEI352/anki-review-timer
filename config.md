## Configuration Options

- **timer_duration_seconds**: How long the front countdown timer runs before automatically revealing the answer (default: `30`)
- **auto_show_answer**: Whether to automatically reveal the answer when front countdown expires (default: `true`)
- **show_pause_indicator**: Show the pause icon prefix when the timer is paused (default: `true`)
- **auto_grade_ease**: What grade to apply when the back countdown expires. Values: `0` (off, show answer only), `1` (Again = fail, default), `2` (Hard), `3` (Good = pass), `4` (Easy)
- **auto_grade_grace_seconds**: Dedicated reading countdown duration (seconds) on the answer screen before auto-grading fires. Resets cleanly whenever the answer appears (default: `30`)
- **front_color**: Color theme for front countdown (`""` for default dynamic Anki FG/Learn/Danger, or `"blue"`, `"green"`, `"yellow"`, `"orange"`, `"purple"`, or custom `#RRGGBB` hex string, default: `""`)
- **back_color**: Color theme for back answer countdown (`"green"` by default, or `"yellow"`, `"orange"`, `"purple"`, `"blue"`, `""` for front dynamic scheme, or custom `#RRGGBB` hex string, default: `"green"`)
