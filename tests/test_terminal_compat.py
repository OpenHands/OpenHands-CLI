from openhands_cli.terminal_compat import (
    TerminalCompatibilityResult,
    check_terminal_compatibility,
    strict_mode_enabled,
)


class _FakeConsole:
    def __init__(self, is_terminal: bool) -> None:
        self.is_terminal = is_terminal


def test_non_terminal_is_incompatible():
    console = _FakeConsole(is_terminal=False)
    result = check_terminal_compatibility(console=console)
    assert isinstance(result, TerminalCompatibilityResult)
    assert result.is_tty is False
    assert "Rich detected" in (result.reason or "")


def test_terminal_is_compatible():
    console = _FakeConsole(is_terminal=True)
    result = check_terminal_compatibility(console=console)
    assert result.is_tty is True
    assert result.reason is None


def test_strict_mode_enabled_from_env_true_values():
    true_values = ["1", "true", "TRUE", "Yes", "on", "ON"]
    for value in true_values:
        env = {"OPENHANDS_CLI_STRICT_TERMINAL": value}
        assert strict_mode_enabled(env) is True


def test_strict_mode_disabled_by_default_and_false_values():
    env = {}
    assert strict_mode_enabled(env) is False

    false_values = ["0", "false", "no", "off", "", " "]
    for value in false_values:
        env = {"OPENHANDS_CLI_STRICT_TERMINAL": value}
        assert strict_mode_enabled(env) is False
