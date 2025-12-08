"""Tests for ACP confirmation mode functionality."""

import pytest
from acp.schema import (
    AllowedOutcome,
    PermissionOption,
    RequestPermissionRequest,
    RequestPermissionResponse,
)

from openhands_cli.acp_impl.confirmation import ask_user_confirmation_acp


class MockACPConnection:
    """Mock ACP connection for testing."""

    def __init__(self, user_choice: str = "accept"):
        """Initialize mock connection.

        Args:
            user_choice: The choice the user will make ('accept', 'reject', etc.)
        """
        self.user_choice = user_choice
        self.last_request = None

    async def requestPermission(
        self, request: RequestPermissionRequest
    ) -> RequestPermissionResponse:
        """Mock permission request."""
        self.last_request = request
        return RequestPermissionResponse(
            outcome=AllowedOutcome(option_id=self.user_choice, outcome="selected")
        )


class MockAction:
    """Mock action for testing."""

    def __init__(self, tool_name: str = "unknown", action: str = ""):
        """Initialize mock action."""
        self.tool_name = tool_name
        self.action = action

    def to_dict(self):
        """Convert to dict."""
        return {"tool_name": self.tool_name, "action": self.action}


class TestAskUserConfirmationACP:
    """Test the ACP confirmation function."""

    @pytest.mark.asyncio
    async def test_approve_action(self):
        """Test that approving actions returns ACCEPT."""
        mock_conn = MockACPConnection(user_choice="accept")
        action = MockAction(tool_name="execute_bash", action="ls -la")

        result = await ask_user_confirmation_acp(
            conn=mock_conn,
            session_id="test-session",
            pending_actions=[action],
        )

        assert result.decision.value == "accept"
        assert mock_conn.last_request is not None
        assert mock_conn.last_request.sessionId == "test-session"
        assert len(mock_conn.last_request.options) >= 2

    @pytest.mark.asyncio
    async def test_reject_action(self):
        """Test that rejecting actions returns REJECT."""
        mock_conn = MockACPConnection(user_choice="reject")
        action = MockAction(tool_name="execute_bash", action="rm -rf /")

        result = await ask_user_confirmation_acp(
            conn=mock_conn,
            session_id="test-session",
            pending_actions=[action],
        )

        assert result.decision.value == "reject"

    @pytest.mark.asyncio
    async def test_multiple_actions(self):
        """Test confirmation with multiple actions."""
        mock_conn = MockACPConnection(user_choice="accept")
        actions = [
            MockAction(tool_name="execute_bash", action="ls"),
            MockAction(tool_name="str_replace_editor", action="view /tmp/file"),
        ]

        result = await ask_user_confirmation_acp(
            conn=mock_conn,
            session_id="test-session",
            pending_actions=actions,
        )

        assert result.decision.value == "accept"
        assert mock_conn.last_request is not None

    @pytest.mark.asyncio
    async def test_empty_actions(self):
        """Test confirmation with no actions."""
        mock_conn = MockACPConnection(user_choice="accept")

        result = await ask_user_confirmation_acp(
            conn=mock_conn,
            session_id="test-session",
            pending_actions=[],
        )

        # Should auto-accept if no actions
        assert result.decision.value == "accept"


class TestConfirmationOptions:
    """Test the permission options structure."""

    def test_permission_options_structure(self):
        """Test that permission options have the correct structure."""
        approve_opt = PermissionOption(
            option_id="approve", name="Approve action", kind="allow_once"
        )
        reject_opt = PermissionOption(
            option_id="reject", name="Reject action", kind="reject_once"
        )

        assert approve_opt.name == "Approve action"
        assert approve_opt.kind == "allow_once"
        assert reject_opt.name == "Reject action"
        assert reject_opt.kind == "reject_once"
