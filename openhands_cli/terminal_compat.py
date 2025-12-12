import os
import sys
from dataclasses import dataclass


@dataclass
class TerminalCompatibilityResult:
    compatible: bool
    reason: str | None
    is_tty: bool


def _env_flag_true(value: str | None) -> bool:
    if value is None:
        return False
    value = value.strip().lower()
    return value in {"1", "true", "yes", "on"}


def check_terminal_compatibility(
    *,
    stdout: object | None = None,
    env: dict[str, str] | None = None,
) -> TerminalCompatibilityResult:
    if stdout is None:
        stdout = sys.stdout
    if env is None:
        env = os.environ  # type: ignore[assignment]

    is_tty = bool(getattr(stdout, "isatty", lambda: False)())

    term = env.get("TERM", "")
    term_lower = term.lower()

    if not is_tty:
        return TerminalCompatibilityResult(
            compatible=False,
            reason="stdout is not a TTY; interactive TUI may not render correctly",
            is_tty=is_tty,
        )

    if term_lower in {"", "dumb"}:
        return TerminalCompatibilityResult(
            compatible=False,
            reason="TERM is unset or 'dumb'; advanced cursor controls may not work",
            is_tty=is_tty,
        )

    return TerminalCompatibilityResult(
        compatible=True,
        reason=None,
        is_tty=is_tty,
    )


def strict_mode_enabled(env: dict[str, str] | None = None) -> bool:
    if env is None:
        env = os.environ  # type: ignore[assignment]
    return _env_flag_true(env.get("OPENHANDS_CLI_STRICT_TERMINAL"))
