from openhands_cli.acp_impl.confirmation import (
    ConfirmationMode,
    get_available_modes,
)

from acp.schema import (
    SessionModeState,
)


def get_session_mode_state(current_mode: ConfirmationMode) -> SessionModeState:
    """Get the session mode state for a given confirmation mode.

    Args:
        current_mode: The current confirmation mode

    Returns:
        SessionModeState with available modes and current mode
    """
    return SessionModeState(
        current_mode_id=current_mode,
        available_modes=get_available_modes(),
    )