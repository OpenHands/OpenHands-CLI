import os
from dataclasses import dataclass
from rich.console import Console

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
    console: Console,
) -> TerminalCompatibilityResult:
    is_terminal = bool(console.is_terminal)

    if not is_terminal:
        return TerminalCompatibilityResult(
            compatible=False,
            reason="Rich detected a non-interactive or unsupported terminal; interactive UI may not render correctly",
            is_tty=is_terminal,
        )

    return TerminalCompatibilityResult(
        compatible=True,
        reason=None,
        is_tty=is_terminal,
    )

def strict_mode_enabled(env: dict[str, str] | None = None) -> bool:
    if env is None:
        env = os.environ  # type: ignore[assignment]
    return _env_flag_true(env.get("OPENHANDS_CLI_STRICT_TERMINAL"))
