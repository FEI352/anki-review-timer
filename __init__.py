"""Review Timer - Shows a countdown timer during card review.

Click the timer to pause/resume.

https://github.com/josh-freeman/anki-review-timer
"""

from aqt import mw, gui_hooks
from aqt.qt import QTimer, QLabel, Qt, QFont, QVBoxLayout, QFrame
from aqt import theme, colors

timer_container = None
timer_label = None
progress_label = None
timer_obj = None
seconds_elapsed = 0
paused = False

# Load config
config = mw.addonManager.getConfig(__name__)
MAX_SECONDS = config.get("timer_duration_seconds", 30)
AUTO_SHOW_ANSWER = config.get("auto_show_answer", True)
SHOW_PAUSE_INDICATOR = config.get("show_pause_indicator", True)
# When the timer expires, optionally grade the card automatically.
# 1=Again, 2=Hard, 3=Good, 4=Easy. None / 0 = show answer only.
AUTO_GRADE_EASE = config.get("auto_grade_ease") or None
# Grace period (seconds) between auto-show-answer and auto-grade.
# Lets the user see the answer for a moment before it's graded.
AUTO_GRADE_GRACE = max(0, config.get("auto_grade_grace_seconds", 1))

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


def _state_for_seconds(secs: int) -> str:
    """Return one of: 'idle', 'mid', 'urgent', 'expired', 'paused'."""
    if paused:
        return "paused"
    remaining = MAX_SECONDS - secs
    if remaining <= 0:
        return "expired"
    ratio = remaining / MAX_SECONDS
    if ratio > 0.5:
        return "idle"
    if ratio > 0.25:
        return "mid"
    return "urgent"


def _fg_for_seconds(secs: int) -> str:
    """Foreground color (text) for the current state, theme-aware."""
    state = _state_for_seconds(secs)
    if state == "paused":
        return _tm().var(colors.FG_DISABLED)
    if state == "expired":
        return _tm().var(colors.FG_FAINT)
    if state == "idle":
        return _tm().var(colors.FG)
    if state == "mid":
        return _tm().var(colors.STATE_LEARN)
    return _tm().var(colors.ACCENT_DANGER)


def _track_color(secs: int) -> str:
    """Color of the empty (track) part of the progress bar."""
    state = _state_for_seconds(secs)
    if state in ("paused", "expired"):
        return _tm().var(colors.BORDER_SUBTLE)
    if state == "idle":
        return _tm().var(colors.FG_FAINT)
    if state == "mid":
        return _tm().var(colors.STATE_LEARN)
    return _tm().var(colors.ACCENT_DANGER)


def _fill_color(secs: int) -> str:
    """Color of the filled part of the progress bar."""
    state = _state_for_seconds(secs)
    if state in ("paused", "expired"):
        return _tm().var(colors.FG_FAINT)
    if state == "idle":
        return _tm().var(colors.BORDER_FOCUS)
    if state == "mid":
        return _tm().var(colors.STATE_LEARN)
    return _tm().var(colors.ACCENT_DANGER)


def _font_size_for_seconds(secs: int) -> int:
    """Bump font size in urgent state for added visual emphasis."""
    return 16 if _state_for_seconds(secs) == "urgent" else 15


def format_time(secs: int) -> str:
    remaining = MAX_SECONDS - secs
    if remaining < 0:
        remaining = 0
    m, s = divmod(remaining, 60)
    return f"{m}:{s:02d}"


# --- UI ---------------------------------------------------------------------

def _apply_stylesheet() -> None:
    """Apply the current theme's stylesheet to the timer container."""
    if timer_container is None:
        return
    tm = _tm()
    text_color = _fg_for_seconds(seconds_elapsed)
    track_color = _track_color(seconds_elapsed)
    font_size = _font_size_for_seconds(seconds_elapsed)

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


def style_label(secs: int) -> None:
    """Update text, color and progress to match current state."""
    if timer_label is None or progress_label is None:
        return
    prefix = "⏸  " if paused and SHOW_PAUSE_INDICATOR else ""
    timer_label.setText(prefix + format_time(secs))

    # Two-tone progress bar via inline HTML spans (theme-aware).
    remaining = max(0, MAX_SECONDS - secs)
    ratio = remaining / MAX_SECONDS if MAX_SECONDS > 0 else 0
    filled_n = round(PROGRESS_BAR_WIDTH * ratio)
    fill_color = _fill_color(secs)
    track_color = _track_color(secs)
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


# --- behaviour --------------------------------------------------------------

def toggle_pause() -> None:
    global paused
    if seconds_elapsed >= MAX_SECONDS:
        return
    paused = not paused
    if paused:
        timer_obj.stop()
    else:
        timer_obj.start(1000)
    style_label(seconds_elapsed)


def update_timer() -> None:
    global seconds_elapsed
    seconds_elapsed += 1
    if timer_container:
        style_label(seconds_elapsed)
    if seconds_elapsed >= MAX_SECONDS:
        timer_obj.stop()
        _handle_timeout()


def _handle_timeout() -> None:
    """Called when the countdown reaches zero.

    By default just shows the answer. If `auto_grade_ease` is configured,
    also grade the card after a short grace period.
    """
    if not (mw.reviewer and mw.state == "review"):
        return
    if mw.reviewer.state == "answer":
        return  # answer already shown — nothing to do

    if AUTO_SHOW_ANSWER:
        mw.reviewer._showAnswer()

    if AUTO_GRADE_EASE and AUTO_GRADE_EASE in (1, 2, 3, 4):
        # Schedule the auto-grade after a grace period so the user gets
        # a moment to see the answer. Stash the timer on the reviewer
        # itself so we can cancel it if the user grades manually first.
        grace_ms = AUTO_GRADE_GRACE * 1000
        grader = QTimer(mw)
        grader.setSingleShot(True)
        grader.timeout.connect(
            lambda e=AUTO_GRADE_EASE: _do_auto_grade(e, grader)
        )
        grader.start(grace_ms)
        # remember so on_show_answer / manual grade can cancel
        mw.reviewer._reviewTimerAutoGrader = grader


def _do_auto_grade(ease: int, grader: "QTimer") -> None:
    """Fire the auto-grade if the card is still waiting on one."""
    try:
        if mw.reviewer and mw.state == "review" \
                and mw.reviewer.state == "answer":
            mw.reviewer._answerCard(ease)
    finally:
        grader.deleteLater()


def _build_widgets() -> None:
    """Lazily construct the timer widget tree on first use."""
    global timer_container, timer_label, progress_label

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


def _position_widget() -> None:
    """Place the container in the top-right corner of the reviewer."""
    if timer_container is None:
        return
    timer_container.adjustSize()
    parent = mw.reviewer.web if mw.reviewer and hasattr(mw.reviewer, "web") else mw
    x = parent.width() - timer_container.width() - 16
    y = 12
    timer_container.move(x, y)
    timer_container.show()
    timer_container.raise_()


def on_show_question(card) -> None:
    global seconds_elapsed, timer_obj, paused

    seconds_elapsed = 0
    paused = False

    if timer_container is None:
        _build_widgets()

    style_label(0)
    _position_widget()

    if timer_obj is None:
        timer_obj = QTimer(mw)
        timer_obj.timeout.connect(update_timer)
    timer_obj.start(1000)


def on_show_answer(card) -> None:
    # Stop the countdown when the answer becomes visible — from here on,
    # the user is reviewing the answer and we don't want the urgency
    # signal. If auto_grade is configured, _handle_timeout will still
    # grade the card after the configured grace period.
    if timer_obj:
        timer_obj.stop()


def _cancel_pending_auto_grade() -> None:
    """Cancel a scheduled auto-grade (called when the user grades manually)."""
    grader = getattr(mw.reviewer, "_reviewTimerAutoGrader", None)
    if grader is not None:
        try:
            grader.stop()
        except Exception:
            pass
        try:
            grader.deleteLater()
        except Exception:
            pass
        mw.reviewer._reviewTimerAutoGrader = None


def on_reviewer_end() -> None:
    if timer_obj:
        timer_obj.stop()
    _cancel_pending_auto_grade()
    if timer_container:
        timer_container.hide()


def on_theme_change() -> None:
    """Re-apply stylesheet when Anki's day/night theme changes."""
    if timer_container and timer_container.isVisible():
        style_label(seconds_elapsed)


def on_reviewer_did_answer(reviewer, card, ease) -> None:
    """Cancel any pending auto-grade — the user graded manually."""
    _cancel_pending_auto_grade()


gui_hooks.reviewer_did_show_question.append(on_show_question)
gui_hooks.reviewer_did_show_answer.append(on_show_answer)
gui_hooks.reviewer_will_end.append(on_reviewer_end)
gui_hooks.theme_did_change.append(on_theme_change)
gui_hooks.reviewer_did_answer_card.append(on_reviewer_did_answer)

