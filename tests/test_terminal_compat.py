import types

from openhands_cli.terminal_compat import (
    TerminalCompatibilityResult,
    check_terminal_compatibility,
    strict_mode_enabled,
)


class _FakeStdout:
    def __init__(self, is_tty: bool) -> None:
        self._is_tty = is_tty

    def isatty(self) -> bool:  # noqa: D401 - simple proxy
        return self._is_tty


def test_non_tty_is_incompatible():
    stdout = _FakeStdout(is_tty=False)
    result = check_terminal_compatibility(stdout=stdout, env={})
    assert isinstance(result, TerminalCompatibilityResult)
    assert result.compatible is False
    assert result.is_tty is False
    assert "not a TTY" in (result.reason or "")


def test_dumb_term_is_incompatible():
    stdout = _FakeStdout(is_tty=True)
    result = check_terminal_compatibility(stdout=stdout, env={"TERM": "dumb"})
    assert result.compatible is False
    assert result.is_tty is True
    assert "dumb" in (result.reason or "")


def test_valid_term_is_compatible():
    stdout = _FakeStdout(is_tty=True)
    result = check_terminal_compatibility(stdout=stdout, env={"TERM": "xterm-256color"})
    assert result.compatible is True
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
