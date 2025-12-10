"""Tests for error display handling with XML special characters."""

import sys
from types import SimpleNamespace

import pytest


def test_error_with_xml_special_characters(monkeypatch):
    """Test that error messages with XML special characters are displayed correctly.

    This reproduces the bug where error messages containing < > & characters
    would cause xml.parsers.expat.ExpatError when the error handler tried to
    display them using prompt_toolkit's HTML formatting.
    """
    # Create an error message with XML special characters (like the diff output)
    error_msg = """The Agent provided is different from the one in persisted state.
Diff: agent_context:
  skills:
    0:
      source: '/path/one' -> '/path/two'
    27: '<missing>' -> {'name': 'user_provided_resources'}
  system_message_suffix: 'working directory: /old' -> 'working directory: /new'"""

    # Mock the agent_chat module
    def mock_run_cli_entry(**kwargs):
        raise ValueError(error_msg)

    fake_agent_chat = SimpleNamespace(run_cli_entry=mock_run_cli_entry)
    monkeypatch.setitem(sys.modules, "openhands_cli.agent_chat", fake_agent_chat)
    monkeypatch.setattr(sys, "argv", ["openhands"], raising=False)

    # Import main after patching
    from openhands_cli.simple_main import main

    # Without the fix, this would raise xml.parsers.expat.ExpatError
    # With the fix, it should handle the error gracefully
    with pytest.raises(ValueError) as exc_info:
        main()

    # Verify the original error was raised (after being handled by error display)
    assert "The Agent provided is different" in str(exc_info.value)

    # Verify that the error handler didn't crash with ExpatError
    # (if it did, we'd get ExpatError instead of ValueError)
    assert exc_info.type is ValueError


def test_error_with_angle_brackets(monkeypatch):
    """Test error messages with angle brackets < > are handled correctly."""
    error_msg = "Error: <missing> field in configuration"

    def mock_run_cli_entry(**kwargs):
        raise RuntimeError(error_msg)

    fake_agent_chat = SimpleNamespace(run_cli_entry=mock_run_cli_entry)
    monkeypatch.setitem(sys.modules, "openhands_cli.agent_chat", fake_agent_chat)
    monkeypatch.setattr(sys, "argv", ["openhands"], raising=False)

    from openhands_cli.simple_main import main

    with pytest.raises(RuntimeError) as exc_info:
        main()

    assert "<missing>" in str(exc_info.value)
    assert exc_info.type is RuntimeError


def test_error_with_ampersand(monkeypatch):
    """Test error messages with ampersands & are handled correctly."""
    error_msg = "Error: command failed with args: foo & bar"

    def mock_run_cli_entry(**kwargs):
        raise RuntimeError(error_msg)

    fake_agent_chat = SimpleNamespace(run_cli_entry=mock_run_cli_entry)
    monkeypatch.setitem(sys.modules, "openhands_cli.agent_chat", fake_agent_chat)
    monkeypatch.setattr(sys, "argv", ["openhands"], raising=False)

    from openhands_cli.simple_main import main

    with pytest.raises(RuntimeError) as exc_info:
        main()

    assert "foo & bar" in str(exc_info.value)
    assert exc_info.type is RuntimeError


def test_error_with_quotes(monkeypatch):
    """Test error messages with quotes are handled correctly."""
    error_msg = 'Error: invalid value "test" provided'

    def mock_run_cli_entry(**kwargs):
        raise RuntimeError(error_msg)

    fake_agent_chat = SimpleNamespace(run_cli_entry=mock_run_cli_entry)
    monkeypatch.setitem(sys.modules, "openhands_cli.agent_chat", fake_agent_chat)
    monkeypatch.setattr(sys, "argv", ["openhands"], raising=False)

    from openhands_cli.simple_main import main

    with pytest.raises(RuntimeError) as exc_info:
        main()

    assert '"test"' in str(exc_info.value)
    assert exc_info.type is RuntimeError
