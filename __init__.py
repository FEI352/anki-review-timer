"""Review Timer - Shows a countdown timer during card review.

Click the timer to pause/resume.

https://github.com/josh-freeman/anki-review-timer
"""

from aqt import mw, gui_hooks
from aqt.qt import QTimer, QLabel, Qt, QFont, QVBoxLayout, QFrame, QObject, QEvent
from aqt import theme, colors

__version__ = "1.3.0"

timer_container = None
timer_label = None
progress_label = None
timer_obj = None
seconds_elapsed = 0
paused = False
_resize_filter = None

# Current phase: "question" (front) or "answer" (back)
current_phase = "question"

# Config variables (loaded via _load_config)
MAX_SECONDS = 30
AUTO_SHOW_ANSWER = True
SHOW_PAUSE_INDICATOR = True
AUTO_GRADE_EASE = 3
AUTO_GRADE_GRACE = 30


def _load_config() -> None:
    """Load and sanitize add-on configuration."""
    global MAX_SECONDS, AUTO_SHOW_ANSWER, SHOW_PAUSE_INDICATOR
    global AUTO_GRADE_EASE, AUTO_GRADE_GRACE

    config = mw.addonManager.getConfig(__name__) or {}
    try:
        MAX_SECONDS = max(1, int(config.get("timer_duration_seconds", 30)))
    except (TypeError, ValueError):
        MAX_SECONDS = 30

    AUTO_SHOW_ANSWER = bool(config.get("auto_show_answer", True))
    SHOW_PAUSE_INDICATOR = bool(config.get("show_pause_indicator", True))

    raw_ease = config.get("auto_grade_ease")
    try:
        parsed_ease = int(raw_ease) if raw_ease is not None else 0
        AUTO_GRADE_EASE = parsed_ease if parsed_ease in (1, 2, 3, 4) else None
    except (TypeError, ValueError):
        AUTO_GRADE_EASE = None

    try:
        AUTO_GRADE_GRACE = max(0, int(config.get("auto_grade_grace_seconds", 30)))
    except (TypeError, ValueError):
        AUTO_GRADE_GRACE = 30


_load_config()


# Progress bar is rendered as a unicode block string. Width is in characters,
# not pixels — keep it short to fit inside the timer card.
PROGRESS_BAR_WIDTH = 8
FILLED_CHAR = "\u2588"   # █ full block
EMPTY_CHAR = "\u2581"    # ▁ lower one eighth block (gives the bar a soft
                         #                                  baseline look)


# --- theme helpers ----------------------------------------------------------

def _tm():
    """Return the active Anki ThemeManager singleton."""
    return theme.theme_manager


def _phase_total_seconds() -> int:
    """Total duration in seconds for the current phase."""
    if current_phase == "answer":
        return AUTO_GRADE_GRACE
    return MAX_SECONDS


def _phase_remaining_seconds() -> int:
    """Remaining seconds for the current phase."""
    total = _phase_total_seconds()
    return max(0, total - seconds_elapsed)


def _state_for_phase() -> str:
    """Return one of: 'idle', 'mid', 'urgent', 'expired', 'paused'."""
    if paused:
        return "paused"
    total = _phase_total_seconds()
    remaining = _phase_remaining_seconds()
    if remaining <= 0:
        return "expired"
    ratio = remaining / total if total > 0 else 0
    if ratio > 0.5:
        return "idle"
    if ratio > 0.25:
        return "mid"
    return "urgent"


def _fg_for_phase() -> str:
    """Foreground color (text) for the current state, theme-aware."""
    state = _state_for_phase()
    if state == "paused":
        return _tm().var(colors.FG_DISABLED)
    if state == "expired":
        return _tm().var(colors.FG_FAINT)
    if state == "idle":
        return _tm().var(colors.FG)
    if state == "mid":
        return _tm().var(colors.STATE_LEARN)
    return _tm().var(colors.ACCENT_DANGER)


def _track_color() -> str:
    """Color of the empty (track) part of the progress bar."""
    state = _state_for_phase()
    if state in ("paused", "expired"):
        return _tm().var(colors.BORDER_SUBTLE)
    if state == "idle":
        return _tm().var(colors.FG_FAINT)
    if state == "mid":
        return _tm().var(colors.STATE_LEARN)
    return _tm().var(colors.ACCENT_DANGER)


def _fill_color() -> str:
    """Color of the filled part of the progress bar."""
    state = _state_for_phase()
    if state in ("paused", "expired"):
        return _tm().var(colors.FG_FAINT)
    if state == "idle":
        return _tm().var(colors.BORDER_FOCUS)
    if state == "mid":
        return _tm().var(colors.STATE_LEARN)
    return _tm().var(colors.ACCENT_DANGER)


def _font_size_for_phase() -> int:
    """Bump font size in urgent state for added visual emphasis."""
    return 16 if _state_for_phase() == "urgent" else 15


def format_time() -> str:
    remaining = _phase_remaining_seconds()
    m, s = divmod(remaining, 60)
    return f"{m}:{s:02d}"


# --- UI ---------------------------------------------------------------------

def _apply_stylesheet() -> None:
    """Apply the current theme's stylesheet to the timer container."""
    if timer_container is None:
        return
    tm = _tm()
    text_color = _fg_for_phase()
    track_color = _track_color()
    font_size = _font_size_for_phase()

    timer_container.setStyleSheet(
        f"""
        QFrame#reviewTimerContainer {{
            background: {tm.var(colors.CANVAS_OVERLAY)};
            border: 1px solid {tm.var(colors.BORDER_SUBTLE)};
            border-radius: 8px;
        }}
        QLabel#reviewTimerText {{
            color: {text_color};
            font-family: 'Menlo', 'Consolas', 'DejaVu Sans Mono', monospace;
            font-size: {font_size}px;
            font-weight: 600;
            background: transparent;
            border: none;
            padding: 6px 12px 2px 12px;
            letter-spacing: 0.5px;
        }}
        QLabel#reviewTimerProgress {{
            color: {track_color};
            font-family: 'Menlo', 'Consolas', 'DejaVu Sans Mono', monospace;
            font-size: 8px;
            background: transparent;
            border: none;
            padding: 0px 12px 6px 12px;
            letter-spacing: 1px;
        }}
        """
    )


def style_label() -> None:
    """Update text, color and progress to match current phase and state."""
    if timer_label is None or progress_label is None:
        return
    prefix = "⏸  " if paused and SHOW_PAUSE_INDICATOR else ""
    timer_label.setText(prefix + format_time())

    # Two-tone progress bar via inline HTML spans (theme-aware).
    total = _phase_total_seconds()
    remaining = _phase_remaining_seconds()
    ratio = remaining / total if total > 0 else 0
    filled_n = round(PROGRESS_BAR_WIDTH * ratio)
    fill_color = _fill_color()
    track_color = _track_color()
    progress_label.setText(
        f"<span style='color:{fill_color}'>"
        f"{FILLED_CHAR * filled_n}</span>"
        f"<span style='color:{track_color}'>"
        f"{EMPTY_CHAR * (PROGRESS_BAR_WIDTH - filled_n)}</span>"
    )
    _apply_stylesheet()


class ClickableLabel(QLabel):
    def mousePressEvent(self, event):
        toggle_pause()


class ReviewerResizeFilter(QObject):
    """Event filter to reposition the timer container when the reviewer resizes."""
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            _position_widget()
        return super().eventFilter(watched, event)


# --- behaviour --------------------------------------------------------------

def toggle_pause() -> None:
    global paused
    if _phase_remaining_seconds() <= 0:
        return
    paused = not paused
    if paused:
        timer_obj.stop()
    else:
        timer_obj.start(1000)
    style_label()


def update_timer() -> None:
    global seconds_elapsed
    seconds_elapsed += 1
    if timer_container:
        style_label()

    total = _phase_total_seconds()
    if seconds_elapsed >= total:
        if current_phase == "question":
            _on_question_timeout()
        elif current_phase == "answer":
            _on_answer_timeout()


def _on_question_timeout() -> None:
    """Triggered when the question phase countdown hits 0."""
    if not (mw.reviewer and mw.state == "review"):
        return

    # Automatically reveal the answer if configured
    if AUTO_SHOW_ANSWER and mw.reviewer.state != "answer":
        mw.reviewer._showAnswer()
        # Note: mw.reviewer._showAnswer() will synchronously trigger
        # the hook reviewer_did_show_answer -> on_show_answer,
        # which cleanly initiates the answer phase!
    else:
        # If auto-show-answer is disabled or answer is already shown,
        # transition to answer phase directly if auto-grade is configured.
        if AUTO_GRADE_EASE and AUTO_GRADE_EASE in (1, 2, 3, 4):
            _start_answer_phase()
        else:
            timer_obj.stop()


def _on_answer_timeout() -> None:
    """Triggered when the answer phase countdown hits 0."""
    timer_obj.stop()
    if AUTO_GRADE_EASE and AUTO_GRADE_EASE in (1, 2, 3, 4):
        _do_auto_grade(AUTO_GRADE_EASE)


def _start_answer_phase() -> None:
    """Cleanly enter the answer phase with its own full grace duration."""
    global current_phase, seconds_elapsed, paused
    current_phase = "answer"
    seconds_elapsed = 0
    paused = False

    if AUTO_GRADE_GRACE <= 0:
        timer_obj.stop()
        if AUTO_GRADE_EASE and AUTO_GRADE_EASE in (1, 2, 3, 4):
            _do_auto_grade(AUTO_GRADE_EASE)
        return

    style_label()
    if timer_obj:
        timer_obj.start(1000)


def _do_auto_grade(ease: int) -> None:
    """Fire the auto-grade if still in reviewer answer state."""
    try:
        if mw.reviewer and mw.state == "review" \
                and mw.reviewer.state == "answer":
            mw.reviewer._answerCard(ease)
    except Exception:
        pass


def _build_widgets() -> None:
    """Lazily construct the timer widget tree on first use."""
    global timer_container, timer_label, progress_label, _resize_filter

    timer_container = QFrame(mw)
    timer_container.setObjectName("reviewTimerContainer")
    timer_container.setCursor(Qt.CursorShape.PointingHandCursor)

    layout = QVBoxLayout(timer_container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    timer_label = ClickableLabel(timer_container)
    timer_label.setObjectName("reviewTimerText")
    timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    timer_label.setFont(QFont("Menlo", 15, QFont.Weight.DemiBold))
    layout.addWidget(timer_label)

    progress_label = QLabel(timer_container)
    progress_label.setObjectName("reviewTimerProgress")
    progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    progress_label.setTextFormat(Qt.TextFormat.RichText)
    progress_label.setFont(QFont("Menlo", 8))
    layout.addWidget(progress_label)

    # Forward clicks on the frame to toggle_pause
    timer_container.mousePressEvent = lambda _e: toggle_pause()

    # Install resize filter on reviewer web view / window
    parent = _get_parent_widget()
    if parent and _resize_filter is None:
        _resize_filter = ReviewerResizeFilter(parent)
        parent.installEventFilter(_resize_filter)


def _get_parent_widget():
    """Get the target parent widget for timer placement."""
    if mw.reviewer and hasattr(mw.reviewer, "web") and mw.reviewer.web:
        return mw.reviewer.web
    return mw


def _position_widget() -> None:
    """Place the container in the top-right corner of the reviewer."""
    if timer_container is None:
        return
    timer_container.adjustSize()
    parent = _get_parent_widget()
    x = parent.width() - timer_container.width() - 16
    y = 12
    timer_container.move(x, y)
    timer_container.show()
    timer_container.raise_()


def on_show_question(card) -> None:
    """Hook: card front is shown."""
    global current_phase, seconds_elapsed, paused, timer_obj

    current_phase = "question"
    seconds_elapsed = 0
    paused = False

    if timer_container is None:
        _build_widgets()

    style_label()
    _position_widget()

    if timer_obj is None:
        timer_obj = QTimer(mw)
        timer_obj.timeout.connect(update_timer)
    timer_obj.start(1000)


def on_show_answer(card) -> None:
    """Hook: card back (answer) is shown, whether manually (space) or via auto-show-answer."""
    # When the answer appears, start the independent answer-phase grace countdown!
    _start_answer_phase()


def on_reviewer_end() -> None:
    """Hook: reviewer exits (deck finished or user exited)."""
    if timer_obj:
        timer_obj.stop()
    if timer_container:
        timer_container.hide()


def on_theme_change() -> None:
    """Hook: Anki day/night theme changed."""
    if timer_container and timer_container.isVisible():
        style_label()


def on_reviewer_did_answer(reviewer, card, ease) -> None:
    """Hook: user answered/graded the card manually."""
    if timer_obj:
        timer_obj.stop()


def on_addon_config_did_change(module: str, conf: dict) -> None:
    """Hook: add-on config changed."""
    if module == __name__:
        _load_config()
        if timer_container and timer_container.isVisible():
            style_label()


gui_hooks.reviewer_did_show_question.append(on_show_question)
gui_hooks.reviewer_did_show_answer.append(on_show_answer)
gui_hooks.reviewer_will_end.append(on_reviewer_end)
gui_hooks.theme_did_change.append(on_theme_change)
gui_hooks.reviewer_did_answer_card.append(on_reviewer_did_answer)

# Register addon_config_did_change only if supported by the running Anki version
if hasattr(gui_hooks, "addon_config_did_change"):
    gui_hooks.addon_config_did_change.append(on_addon_config_did_change)
elif hasattr(mw.addonManager, "addon_config_did_change"):
    try:
        mw.addonManager.addon_config_did_change.append(on_addon_config_did_change)
    except Exception:
        pass
