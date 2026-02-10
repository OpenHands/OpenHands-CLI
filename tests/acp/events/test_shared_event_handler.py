"""Tests for ACP shared event handler hook rejection functionality."""

import pytest

from openhands.sdk.event import AgentErrorEvent, UserRejectObservation
from openhands_cli.acp_impl.events.shared_event_handler import _is_hook_rejection


class TestACPHookRejectionDetection:
    """Tests for hook rejection detection in ACP shared event handler."""

    def test_is_hook_rejection_detects_blocked_by_hook(self):
        """Test that 'blocked by hook' pattern is detected."""
        event = UserRejectObservation(
            tool_name="terminal",
            tool_call_id="call_1",
            action_id="action_1",
            rejection_reason="Blocked by hook",
        )
        assert _is_hook_rejection(event) is True

    def test_is_hook_rejection_detects_hook_blocked(self):
        """Test that 'hook blocked' pattern is detected."""
        event = UserRejectObservation(
            tool_name="terminal",
            tool_call_id="call_1",
            action_id="action_1",
            rejection_reason="This action was hook blocked for security",
        )
        assert _is_hook_rejection(event) is True

    def test_is_hook_rejection_case_insensitive(self):
        """Test that hook detection is case insensitive."""
        event = UserRejectObservation(
            tool_name="terminal",
            tool_call_id="call_1",
            action_id="action_1",
            rejection_reason="BLOCKED BY HOOK",
        )
        assert _is_hook_rejection(event) is True

    def test_is_hook_rejection_returns_false_for_user_rejection(self):
        """Test that user rejections are not detected as hook rejections."""
        event = UserRejectObservation(
            tool_name="terminal",
            tool_call_id="call_1",
            action_id="action_1",
            rejection_reason="User rejected the action",
        )
        assert _is_hook_rejection(event) is False

    def test_is_hook_rejection_returns_false_for_custom_reason(self):
        """Test that custom rejection reasons are not detected as hooks."""
        event = UserRejectObservation(
            tool_name="terminal",
            tool_call_id="call_1",
            action_id="action_1",
            rejection_reason="I don't want to run this dangerous command",
        )
        assert _is_hook_rejection(event) is False
