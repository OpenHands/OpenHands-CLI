"""Tests for ACP shared event handler hook rejection detection."""

from openhands.sdk.event import AgentErrorEvent, UserRejectObservation
from openhands_cli.acp_impl.events.shared_event_handler import (
    HOOK_BLOCKED_HEADER,
    _is_hook_rejection,
)


class TestACPHookRejectionDetection:
    """Tests for hook rejection detection in ACP shared event handler.

    Note: These tests use model_copy() to add rejection_source field since the
    SDK version with this field may not be installed yet. The _is_hook_rejection
    function uses getattr() for backwards compatibility.
    """

    def test_is_hook_rejection_with_hook_source(self):
        """Test _is_hook_rejection returns True for hook rejections."""
        base_event = UserRejectObservation(
            action_id="test_action_id",
            tool_name="terminal",
            tool_call_id="call_1",
            rejection_reason="Blocked by security hook",
        )
        event = base_event.model_copy(update={"rejection_source": "hook"})
        assert _is_hook_rejection(event) is True

    def test_is_hook_rejection_with_user_source(self):
        """Test _is_hook_rejection returns False for user rejections."""
        base_event = UserRejectObservation(
            action_id="test_action_id",
            tool_name="terminal",
            tool_call_id="call_1",
            rejection_reason="User rejected the action",
        )
        event = base_event.model_copy(update={"rejection_source": "user"})
        assert _is_hook_rejection(event) is False

    def test_is_hook_rejection_with_no_source_field(self):
        """Test _is_hook_rejection returns False when rejection_source not present."""
        event = UserRejectObservation(
            action_id="test_action_id",
            tool_name="terminal",
            tool_call_id="call_1",
            rejection_reason="User rejected the action",
        )
        assert _is_hook_rejection(event) is False

    def test_is_hook_rejection_with_agent_error_event(self):
        """Test _is_hook_rejection returns False for AgentErrorEvent."""
        event = AgentErrorEvent(
            error="Something went wrong",
            tool_name="terminal",
            tool_call_id="call_1",
        )
        assert _is_hook_rejection(event) is False

    def test_hook_blocked_header_format(self):
        """Test HOOK_BLOCKED_HEADER has expected format."""
        assert "⚡" in HOOK_BLOCKED_HEADER
        assert "Hook" in HOOK_BLOCKED_HEADER
        assert HOOK_BLOCKED_HEADER.endswith("\n")
