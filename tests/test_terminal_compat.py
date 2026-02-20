from rich.console import Console

from openhands_cli.terminal_compat import (
    TerminalCompatibilityResult,
    check_terminal_compatibility,
)


def test_non_terminal_is_incompatible():
    console = Console(force_terminal=False)
    result = check_terminal_compatibility(console=console)
    assert isinstance(result, TerminalCompatibilityResult)
    assert result.is_tty is False
    assert "Rich detected" in (result.reason or "")


def test_terminal_is_compatible():
    console = Console(force_terminal=True)
    result = check_terminal_compatibility(console=console)
    assert result.is_tty is True
    assert result.reason is None
