import types
from unittest.mock import MagicMock

import pytest

import openhands_cli.tui.widgets.status_line as status_line_module

# Adjust the import path to wherever this file actually lives
from openhands_cli.tui.widgets.status_line import (
    InfoStatusLine,
    WorkingStatusLine,
)


@pytest.fixture
def dummy_app() -> object:
    """Minimal 'app' object to satisfy the widgets' expectations."""
    app = types.SimpleNamespace()
    # For WorkingStatusLine
    app.conversation_running_signal = types.SimpleNamespace(subscribe=MagicMock())
    # For InfoStatusLine
    app.input_field = types.SimpleNamespace(
        mutliline_mode_status=types.SimpleNamespace(subscribe=MagicMock())
    )
    return app


# ----- WorkingStatusLine tests -----


def test_conversation_start_sets_timer_and_flags(dummy_app, monkeypatch):
    """Starting a conversation marks working, sets start time, and creates a timer."""
    widget = WorkingStatusLine(app=dummy_app)

    fake_timer = MagicMock()
    set_interval_mock = MagicMock(return_value=fake_timer)
    monkeypatch.setattr(widget, "set_interval", set_interval_mock)

    assert widget._conversation_start_time is None
    assert widget._timer is None
    assert widget._is_working is False

    widget._on_conversation_state_changed(True)

    assert widget._is_working is True
    assert widget._conversation_start_time is not None
    set_interval_mock.assert_called_once()
    assert widget._timer is fake_timer


def test_conversation_stop_stops_timer_and_clears_state(dummy_app, monkeypatch):
    """Stopping a conversation stops the timer, clears state, and updates text."""
    widget = WorkingStatusLine(app=dummy_app)

    fake_timer = MagicMock()
    widget._timer = fake_timer
    widget._conversation_start_time = 123.0
    widget._is_working = True

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    widget._on_conversation_state_changed(False)

    assert widget._is_working is False
    assert widget._conversation_start_time is None
    fake_timer.stop.assert_called_once()
    assert widget._timer is None
    update_text_mock.assert_called_once()


def test_on_tick_increments_working_frame_and_updates_text(dummy_app, monkeypatch):
    """Tick while working advances the spinner frame and triggers a text update."""
    widget = WorkingStatusLine(app=dummy_app)

    widget._conversation_start_time = 0.0  # non-None to enable ticking
    widget._is_working = True
    widget._working_frame = 0

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    widget._on_tick()

    assert widget._working_frame == 1
    update_text_mock.assert_called_once()


def test_get_working_text_includes_spinner_and_elapsed_seconds(dummy_app, monkeypatch):
    """_get_working_text returns spinner + 'Working' + elapsed seconds when active."""
    widget = WorkingStatusLine(app=dummy_app)

    # Fix "current" time and start time to make elapsed deterministic.
    start_time = 10.0
    now_time = 15.4  # ~5 seconds later
    widget._conversation_start_time = start_time
    widget._is_working = True
    widget._working_frame = 0  # should map to the first spinner frame "⠋"

    monkeypatch.setattr(status_line_module.time, "time", lambda: now_time)

    text = widget._get_working_text()

    # Exact text should match the first frame and rounded elapsed seconds.
    assert text == "⠋ Working (5s • ESC: pause)"


def test_get_working_text_when_not_started_returns_empty(dummy_app, monkeypatch):
    """If no conversation start time is set, working text should be empty."""
    widget = WorkingStatusLine(app=dummy_app)

    widget._conversation_start_time = None
    widget._is_working = True  # even if working flag is true, no start time => no text

    text = widget._get_working_text()
    assert text == ""


# ----- InfoStatusLine tests -----


def test_get_work_dir_display_shortens_home_to_tilde(dummy_app, monkeypatch):
    """_get_work_dir_display replaces the home prefix with '~' when applicable."""
    # Pretend the home directory is /home/testuser
    monkeypatch.setattr(
        status_line_module.os.path,
        "expanduser",
        lambda path: "/home/testuser" if path == "~" else path,
    )
    # Set WORK_DIR to be inside that home directory
    monkeypatch.setattr(
        status_line_module,
        "WORK_DIR",
        "/home/testuser/projects/openhands",
    )

    widget = InfoStatusLine(app=dummy_app)
    display = widget._get_work_dir_display()

    assert display.startswith("~")
    assert "projects/openhands" in display
    # Just to be safe, ensure the raw /home/testuser prefix is gone
    assert "/home/testuser" not in display


def test_handle_multiline_mode_updates_indicator_and_refreshes(dummy_app, monkeypatch):
    """Toggling multiline mode updates the mode indicator and refreshes text."""
    widget = InfoStatusLine(app=dummy_app)

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    # Enable multiline mode
    widget._on_handle_mutliline_mode(True)
    assert widget.mode_indicator == "[Multi-line: Ctrl+J to submit]"
    update_text_mock.assert_called_once()

    update_text_mock.reset_mock()

    # Disable multiline mode
    widget._on_handle_mutliline_mode(False)
    assert widget.mode_indicator == "[Ctrl+L for multi-line]"
    update_text_mock.assert_called_once()


def test_update_text_uses_mode_indicator_and_work_dir(dummy_app, monkeypatch):
    """_update_text composes the status line from mode indicator and work dir."""
    widget = InfoStatusLine(app=dummy_app)

    widget.mode_indicator = "[test-mode]"
    widget.work_dir_display = "~/my-dir"

    update_mock = MagicMock()
    monkeypatch.setattr(widget, "update", update_mock)

    widget._update_text()

    update_mock.assert_called_once_with("[test-mode] • ~/my-dir")
