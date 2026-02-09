from unittest.mock import MagicMock

from openhands.sdk.llm.utils.metrics import Metrics, TokenUsage

# Adjust the import path to wherever this file actually lives
from openhands_cli.tui.widgets.status_line import (
    InfoStatusLine,
    WorkingStatusLine,
)
from openhands_cli.utils import abbreviate_number, format_cost


def create_mock_metrics(
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cache_read_tokens: int = 0,
    context_window: int = 0,
    accumulated_cost: float = 0.0,
    last_request_prompt_tokens: int = 0,
) -> Metrics:
    """Create a Metrics object for testing."""
    metrics = Metrics()
    metrics.accumulated_cost = accumulated_cost
    metrics.accumulated_token_usage = TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cache_read_tokens=cache_read_tokens,
        context_window=context_window,
    )
    if last_request_prompt_tokens > 0:
        metrics.token_usages = [TokenUsage(prompt_tokens=last_request_prompt_tokens)]
    return metrics


# ----- WorkingStatusLine tests -----


def test_on_tick_increments_working_frame_and_updates_text(monkeypatch):
    """Tick while working advances the spinner frame and triggers a text update."""
    widget = WorkingStatusLine()

    # Set reactive properties directly
    widget.running = True
    widget._working_frame = 0

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    widget._on_tick()

    assert widget._working_frame == 1
    update_text_mock.assert_called_once()


def test_get_working_text_includes_spinner_and_elapsed_seconds(monkeypatch):
    """_get_working_text returns spinner + 'Working' + elapsed seconds when active."""
    widget = WorkingStatusLine()

    # Set reactive properties directly
    widget.running = True
    widget.elapsed_seconds = 5
    widget._working_frame = 0  # should map to the first spinner frame "⠋"

    text = widget._get_working_text()

    # Exact text should match the first frame and elapsed seconds.
    assert text == "⠋ Working (5s • ESC: pause)"


def test_get_working_text_when_not_running_returns_empty(monkeypatch):
    """If not running, working text should be empty."""
    widget = WorkingStatusLine()

    widget.running = False
    widget.elapsed_seconds = 10  # even with elapsed time, not running => no text

    text = widget._get_working_text()
    assert text == ""


def test_watch_running_updates_text(monkeypatch):
    """Changing running state triggers text update."""
    widget = WorkingStatusLine()

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    widget.watch_running(True)

    update_text_mock.assert_called_once()


def test_elapsed_seconds_shown_in_working_text(monkeypatch):
    """elapsed_seconds value is included in the working status text."""
    widget = WorkingStatusLine()
    widget.running = True  # Must be running to show timer
    widget.elapsed_seconds = 42

    # The working text should include the elapsed seconds
    working_text = widget._get_working_text()
    assert "42s" in working_text


# ----- InfoStatusLine tests -----


def test_get_work_dir_display_shortens_home_to_tilde(mock_locations, monkeypatch):
    """_get_work_dir_display replaces the home prefix with '~' when applicable."""
    work_dir_inside_home = mock_locations.home_dir / "projects" / "my-project"
    work_dir_inside_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OPENHANDS_WORK_DIR", str(work_dir_inside_home))

    widget = InfoStatusLine()
    display = widget._get_work_dir_display()

    assert display.startswith("~")
    assert "projects/my-project" in display
    assert str(mock_locations.home_dir) not in display


def test_mode_indicator_property_multiline(monkeypatch):
    """mode_indicator property returns correct text based on is_multiline_mode."""
    widget = InfoStatusLine()

    # Default (single-line mode)
    widget.is_multiline_mode = False
    assert (
        widget.mode_indicator == "\\[Ctrl+L for multi-line • Ctrl+X for custom editor]"
    )

    # Multiline mode
    widget.is_multiline_mode = True
    assert (
        widget.mode_indicator
        == "\\[Multi-line: Ctrl+J to submit • Ctrl+X for custom editor]"
    )


def test_watch_is_multiline_mode_updates_text(monkeypatch):
    """Changing is_multiline_mode triggers text update."""
    widget = InfoStatusLine()

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    widget.watch_is_multiline_mode(True)

    update_text_mock.assert_called_once()


def test_update_text_uses_work_dir_and_metrics(monkeypatch):
    """_update_text composes the status line with metrics right-aligned in grey."""
    widget = InfoStatusLine()

    widget.work_dir_display = "~/my-dir"
    widget.metrics = None  # No metrics yet

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


def test_update_text_shows_all_metrics(monkeypatch):
    """_update_text shows context (current/total), cost, and token details in grey."""
    widget = InfoStatusLine()

    widget.work_dir_display = "~/my-dir"
    # Create metrics: 5.22M input, 42.01K output, 77% cache, 50K ctx, 128K win
    widget.metrics = create_mock_metrics(
        prompt_tokens=5220000,
        completion_tokens=42010,
        cache_read_tokens=int(5220000 * 0.77),  # 77% cache hit
        context_window=128000,
        accumulated_cost=10.5507,
        last_request_prompt_tokens=50000,
    )

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


def test_format_metrics_display_with_context_current_and_total():
    """_format_metrics_display shows current context / total context window."""
    widget = InfoStatusLine()

    widget.metrics = create_mock_metrics(
        prompt_tokens=1000,
        completion_tokens=500,
        cache_read_tokens=500,  # 50% cache hit
        context_window=200000,
        accumulated_cost=0.05,
        last_request_prompt_tokens=50000,
    )

    result = widget._format_metrics_display()

    assert "ctx 50K / 200K" in result
    assert "$ 0.0500" in result
    assert "↑ 1K" in result
    assert "↓ 500" in result
    assert "cache 50%" in result


def test_format_metrics_display_with_context_current_only():
    """_format_metrics_display shows only current context when total is unavailable."""
    widget = InfoStatusLine()

    widget.metrics = create_mock_metrics(
        prompt_tokens=1000,
        completion_tokens=500,
        cache_read_tokens=500,
        context_window=0,  # No total available
        accumulated_cost=0.05,
        last_request_prompt_tokens=50000,
    )

    result = widget._format_metrics_display()

    assert "ctx 50K" in result
    assert "/ " not in result  # No total shown
    assert "$ 0.0500" in result


def test_format_metrics_display_without_context():
    """_format_metrics_display shows N/A when no context info available."""
    widget = InfoStatusLine()

    widget.metrics = create_mock_metrics(
        prompt_tokens=1000,
        completion_tokens=500,
        cache_read_tokens=500,
        context_window=0,
        accumulated_cost=0.05,
        last_request_prompt_tokens=0,  # No last request
    )

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


# ----- InfoStatusLine reactive watcher tests -----


def test_watch_metrics_updates_text(monkeypatch):
    """Changing metrics triggers text update."""
    widget = InfoStatusLine()

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    metrics = create_mock_metrics(prompt_tokens=1000, accumulated_cost=0.5)
    widget.watch_metrics(metrics)

    update_text_mock.assert_called_once()


def test_watch_metrics_with_none_updates_text(monkeypatch):
    """Changing metrics to None triggers text update."""
    widget = InfoStatusLine()

    update_text_mock = MagicMock()
    monkeypatch.setattr(widget, "_update_text", update_text_mock)

    widget.watch_metrics(None)

    update_text_mock.assert_called_once()
