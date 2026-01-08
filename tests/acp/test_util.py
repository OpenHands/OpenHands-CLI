"""Tests for ACP agent utility functions."""

import pytest

from openhands_cli.acp_impl.agent.util import get_session_mode_state


class TestGetSessionModeState:
    """Tests for the get_session_mode_state function."""

    @pytest.mark.parametrize(
        "current_mode,expected_mode_id",
        [
            ("always-ask", "always-ask"),
            ("always-approve", "always-approve"),
            ("llm-approve", "llm-approve"),
        ],
    )
    def test_returns_correct_current_mode(self, current_mode, expected_mode_id):
        """Test get_session_mode_state returns correct current mode ID."""
        state = get_session_mode_state(current_mode)
        assert state.current_mode_id == expected_mode_id

    @pytest.mark.parametrize(
        "current_mode",
        ["always-ask", "always-approve", "llm-approve"],
    )
    def test_returns_all_available_modes(self, current_mode):
        """Test get_session_mode_state returns all available modes."""
        state = get_session_mode_state(current_mode)

        assert state.available_modes is not None
        assert len(state.available_modes) == 3

        mode_ids = {mode.id for mode in state.available_modes}
        assert mode_ids == {"always-ask", "always-approve", "llm-approve"}

    @pytest.mark.parametrize(
        "current_mode",
        ["always-ask", "always-approve", "llm-approve"],
    )
    def test_available_modes_have_required_fields(self, current_mode):
        """Test all available modes have required fields (id, name, description)."""
        state = get_session_mode_state(current_mode)

        for mode in state.available_modes:
            assert mode.id is not None and mode.id != ""
            assert mode.name is not None and mode.name != ""
            assert mode.description is not None and mode.description != ""
