from pydantic import BaseModel
from rich.console import Console


class TerminalCompatibilityResult(BaseModel):
    is_tty: bool
    reason: str | None = None


def check_terminal_compatibility(
    *,
    console: Console,
) -> TerminalCompatibilityResult:
    is_terminal = bool(console.is_terminal)

    if not is_terminal:
        return TerminalCompatibilityResult(
            reason=(
                "Rich detected a non-interactive or unsupported terminal; "
                "interactive UI may not render correctly"
            ),
            is_tty=is_terminal,
        )

    return TerminalCompatibilityResult(
        is_tty=is_terminal,
    )
