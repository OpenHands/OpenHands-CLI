import types
from unittest.mock import MagicMock

import pytest

import openhands_cli.tui.widgets.status_line as status_line_module

# Adjust the import path to wherever this file actually lives
from openhands_cli.tui.widgets.status_line import (
    InfoStatusLine,
    WorkingStatusLine,
)
from openhands_cli.utils import abbreviate_number, format_cost


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
    # For metrics display
    app.conversation_runner = None
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
    assert (
        widget.mode_indicator
        == "\\[Multi-line: Ctrl+J to submit • Ctrl+X for custom editor]"
    )
    update_text_mock.assert_called_once()

    update_text_mock.reset_mock()

    # Disable multiline mode
    widget._on_handle_mutliline_mode(False)
    assert (
        widget.mode_indicator == "\\[Ctrl+L for multi-line • Ctrl+X for custom editor]"
    )
    update_text_mock.assert_called_once()


def test_update_text_uses_work_dir_and_metrics(dummy_app, monkeypatch):
    """_update_text composes the status line with metrics right-aligned in grey."""
    widget = InfoStatusLine(app=dummy_app)

    widget.work_dir_display = "~/my-dir"
    widget._input_tokens = 0
    widget._output_tokens = 0
    widget._cache_hit_rate = "N/A"
    widget._last_request_input_tokens = 0
    widget._context_window = 0
    widget._accumulated_cost = 0.0

    update_mock = MagicMock()
    monkeypatch.setattr(widget, "update", update_mock)

    widget._update_text()

    # Check that update was called with the right structure
    update_mock.assert_called_once()
    call_arg = update_mock.call_args[0][0]
    # Should contain left part (mode indicator and work dir)
    assert "\\[Ctrl+L for multi-line • Ctrl+X for custom editor] • ~/my-dir" in call_arg
    # Should contain grey markup around metrics
    assert "[grey50]" in call_arg
    assert "[/grey50]" in call_arg
    # Should contain metrics
    assert "ctx N/A" in call_arg
    assert "$ 0.00" in call_arg


def test_update_text_shows_all_metrics(dummy_app, monkeypatch):
    """_update_text shows context (current/total), cost, and token details in grey."""
    widget = InfoStatusLine(app=dummy_app)

    widget.work_dir_display = "~/my-dir"
    widget._input_tokens = 5220000  # 5.22M accumulated
    widget._output_tokens = 42010  # 42.01K
    widget._cache_hit_rate = "77%"
    widget._last_request_input_tokens = 50000  # 50K current context
    widget._context_window = 128000  # 128K total
    widget._accumulated_cost = 10.5507

    update_mock = MagicMock()
    monkeypatch.setattr(widget, "update", update_mock)

    widget._update_text()

    # Check that update was called with the right structure
    update_mock.assert_called_once()
    call_arg = update_mock.call_args[0][0]
    # Should contain left part
    assert "\\[Ctrl+L for multi-line • Ctrl+X for custom editor] • ~/my-dir" in call_arg
    # Should contain grey markup
    assert "[grey50]" in call_arg
    assert "[/grey50]" in call_arg
    # Should contain all metrics
    assert "ctx 50K / 128K" in call_arg
    assert "$ 10.5507" in call_arg
    assert "↑ 5.22M" in call_arg
    assert "↓ 42.01K" in call_arg
    assert "cache 77%" in call_arg


def test_format_metrics_display_with_context_current_and_total(dummy_app):
    """_format_metrics_display shows current context / total context window."""
    widget = InfoStatusLine(app=dummy_app)

    widget._input_tokens = 1000
    widget._output_tokens = 500
    widget._cache_hit_rate = "50%"
    widget._last_request_input_tokens = 50000  # 50K current
    widget._context_window = 200000  # 200K total
    widget._accumulated_cost = 0.05

    result = widget._format_metrics_display()

    assert "ctx 50K / 200K" in result
    assert "$ 0.0500" in result
    assert "↑ 1K" in result
    assert "↓ 500" in result
    assert "cache 50%" in result


def test_format_metrics_display_with_context_current_only(dummy_app):
    """_format_metrics_display shows only current context when total is unavailable."""
    widget = InfoStatusLine(app=dummy_app)

    widget._input_tokens = 1000
    widget._output_tokens = 500
    widget._cache_hit_rate = "50%"
    widget._last_request_input_tokens = 50000  # 50K current
    widget._context_window = 0  # No total available
    widget._accumulated_cost = 0.05

    result = widget._format_metrics_display()

    assert "ctx 50K" in result
    assert "/ " not in result  # No total shown
    assert "$ 0.0500" in result


def test_format_metrics_display_without_context(dummy_app):
    """_format_metrics_display shows N/A when no context info available."""
    widget = InfoStatusLine(app=dummy_app)

    widget._input_tokens = 1000
    widget._output_tokens = 500
    widget._cache_hit_rate = "50%"
    widget._last_request_input_tokens = 0
    widget._context_window = 0
    widget._accumulated_cost = 0.05

    result = widget._format_metrics_display()

    assert "ctx N/A" in result
    assert "$ 0.0500" in result


# ----- abbreviate_number tests -----


def test_abbreviate_number_small():
    """abbreviate_number returns raw number for small values."""
    assert abbreviate_number(0) == "0"
    assert abbreviate_number(999) == "999"
    assert abbreviate_number(100) == "100"


def test_abbreviate_number_thousands():
    """abbreviate_number returns K suffix for thousands."""
    assert abbreviate_number(1000) == "1K"
    assert abbreviate_number(1500) == "1.5K"
    assert abbreviate_number(42010) == "42.01K"
    assert abbreviate_number(999999) == "1000K"


def test_abbreviate_number_millions():
    """abbreviate_number returns M suffix for millions."""
    assert abbreviate_number(1000000) == "1M"
    assert abbreviate_number(5220000) == "5.22M"
    assert abbreviate_number(1500000) == "1.5M"


def test_abbreviate_number_billions():
    """abbreviate_number returns B suffix for billions."""
    assert abbreviate_number(1000000000) == "1B"
    assert abbreviate_number(2500000000) == "2.5B"


# ----- format_cost tests -----


def test_format_cost_zero():
    """format_cost returns 0.00 for zero cost."""
    assert format_cost(0.0) == "0.00"


def test_format_cost_negative():
    """format_cost returns 0.00 for negative cost."""
    assert format_cost(-0.5) == "0.00"


def test_format_cost_positive():
    """format_cost returns formatted cost for positive values."""
    assert format_cost(0.1234) == "0.1234"
    assert format_cost(1.5) == "1.5000"
    assert format_cost(0.0001) == "0.0001"
    assert format_cost(10.5507) == "10.5507"


# ----- InfoStatusLine metrics update tests -----


def test_conversation_state_changed_starts_metrics_timer(dummy_app, monkeypatch):
    """Starting a conversation starts the metrics update timer."""
    widget = InfoStatusLine(app=dummy_app)

    fake_timer = MagicMock()
    set_interval_mock = MagicMock(return_value=fake_timer)
    monkeypatch.setattr(widget, "set_interval", set_interval_mock)

    assert widget._metrics_update_timer is None

    widget._on_conversation_state_changed(True)

    set_interval_mock.assert_called_once()
    assert widget._metrics_update_timer is fake_timer


def test_conversation_state_changed_stops_metrics_timer(dummy_app, monkeypatch):
    """Stopping a conversation stops the metrics update timer."""
    widget = InfoStatusLine(app=dummy_app)

    fake_timer = MagicMock()
    widget._metrics_update_timer = fake_timer

    update_metrics_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_metrics", update_metrics_mock)

    widget._on_conversation_state_changed(False)

    fake_timer.stop.assert_called_once()
    assert widget._metrics_update_timer is None
    update_metrics_mock.assert_called_once()


def test_update_metrics_gets_all_metrics_from_conversation_runner(
    dummy_app, monkeypatch
):
    """_update_metrics retrieves all metrics from conversation runner's visualizer."""
    widget = InfoStatusLine(app=dummy_app)

    # Mock accumulated token usage
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 5000
    mock_usage.completion_tokens = 1000
    mock_usage.context_window = 128000
    mock_usage.cache_read_tokens = 2500  # 50% cache hit

    # Mock last request token usage (for current context)
    mock_last_usage = MagicMock()
    mock_last_usage.prompt_tokens = 3000  # Last request input tokens

    # Mock the conversation runner and its visualizer
    mock_combined_metrics = MagicMock()
    mock_combined_metrics.accumulated_cost = 0.5678
    mock_combined_metrics.accumulated_token_usage = mock_usage
    mock_combined_metrics.token_usages = [mock_last_usage]

    mock_stats = MagicMock()
    mock_stats.get_combined_metrics.return_value = mock_combined_metrics

    mock_visualizer = MagicMock()
    mock_visualizer.conversation_stats = mock_stats

    mock_runner = MagicMock()
    mock_runner.visualizer = mock_visualizer

    dummy_app.conversation_runner = mock_runner

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    widget._update_metrics()

    assert widget._accumulated_cost == 0.5678
    assert widget._input_tokens == 5000
    assert widget._output_tokens == 1000
    assert widget._context_window == 128000
    assert widget._last_request_input_tokens == 3000
    assert widget._cache_hit_rate == "50%"
    update_text_mock.assert_called_once()


def test_update_metrics_handles_no_conversation_runner(dummy_app, monkeypatch):
    """_update_metrics handles case when conversation runner is None."""
    widget = InfoStatusLine(app=dummy_app)
    widget._accumulated_cost = 0.0
    widget._input_tokens = 0

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    widget._update_metrics()

    assert widget._accumulated_cost == 0.0
    assert widget._input_tokens == 0
    update_text_mock.assert_called_once()


def test_update_metrics_handles_no_stats(dummy_app, monkeypatch):
    """_update_metrics handles case when conversation stats is None."""
    widget = InfoStatusLine(app=dummy_app)
    widget._accumulated_cost = 0.0

    mock_visualizer = MagicMock()
    mock_visualizer.conversation_stats = None

    mock_runner = MagicMock()
    mock_runner.visualizer = mock_visualizer

    dummy_app.conversation_runner = mock_runner

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    widget._update_metrics()

    assert widget._accumulated_cost == 0.0
    update_text_mock.assert_called_once()


def test_update_metrics_handles_zero_prompt_tokens(dummy_app, monkeypatch):
    """_update_metrics handles zero prompt tokens for cache hit calculation."""
    widget = InfoStatusLine(app=dummy_app)

    # Mock token usage with zero prompt tokens
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 0
    mock_usage.completion_tokens = 100
    mock_usage.context_window = 0
    mock_usage.cache_read_tokens = 0

    mock_combined_metrics = MagicMock()
    mock_combined_metrics.accumulated_cost = 0.01
    mock_combined_metrics.accumulated_token_usage = mock_usage
    mock_combined_metrics.token_usages = []  # No token usages

    mock_stats = MagicMock()
    mock_stats.get_combined_metrics.return_value = mock_combined_metrics

    mock_visualizer = MagicMock()
    mock_visualizer.conversation_stats = mock_stats

    mock_runner = MagicMock()
    mock_runner.visualizer = mock_visualizer

    dummy_app.conversation_runner = mock_runner

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    widget._update_metrics()

    assert widget._cache_hit_rate == "N/A"
    assert widget._last_request_input_tokens == 0
    update_text_mock.assert_called_once()
