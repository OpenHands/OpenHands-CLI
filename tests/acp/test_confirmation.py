"""Tests for ACP confirmation mode functionality."""

from typing import Any

import pytest
from acp.schema import (
    AllowedOutcome,
    CreateTerminalResponse,
    DeniedOutcome,
    EnvVariable,
    KillTerminalCommandResponse,
    PermissionOption,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    TerminalOutputResponse,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)

from openhands_cli.acp_impl.confirmation import (
    PERMISSION_OPTIONS,
    ask_user_confirmation_acp,
)
from openhands_cli.user_actions.types import UserConfirmation


class MockACPConnection:
    """Mock ACP connection for testing that implements the Client protocol."""

    def __init__(
        self, user_choice: str = "accept", should_deny: bool = False, fail: bool = False
    ):
        """Initialize mock connection.

        Args:
            user_choice: The choice the user will make ('accept', 'reject', etc.)
            should_deny: If True, return DeniedOutcome instead of AllowedOutcome
            fail: If True, raise an exception
        """
        self.user_choice = user_choice
        self.should_deny = should_deny
        self.fail = fail
        self.last_request = None

    async def request_permission(
        self,
        options: list[PermissionOption],
        session_id: str,
        tool_call: Any,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        """Mock permission request."""
        if self.fail:
            raise RuntimeError("Mock connection failure")

        self.last_request = {
            "options": options,
            "session_id": session_id,
            "tool_call": tool_call,
        }

        if self.should_deny:
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))
        else:
            return RequestPermissionResponse(
                outcome=AllowedOutcome(option_id=self.user_choice, outcome="selected")
            )

    # Stub implementations for other Client protocol methods (not used in tests)
    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        """Stub method."""
        pass

    async def write_text_file(
        self, content: str, path: str, session_id: str, **kwargs: Any
    ) -> WriteTextFileResponse | None:
        """Stub method."""
        return None

    async def read_text_file(
        self,
        path: str,
        session_id: str,
        limit: int | None = None,
        line: int | None = None,
        **kwargs: Any,
    ) -> ReadTextFileResponse:
        """Stub method."""
        raise NotImplementedError("Not used in these tests")

    async def create_terminal(
        self,
        command: str,
        session_id: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: list[EnvVariable] | None = None,
        output_byte_limit: int | None = None,
        **kwargs: Any,
    ) -> CreateTerminalResponse:
        """Stub method."""
        raise NotImplementedError("Not used in these tests")

    async def terminal_output(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> TerminalOutputResponse:
        """Stub method."""
        raise NotImplementedError("Not used in these tests")

    async def release_terminal(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> ReleaseTerminalResponse | None:
        """Stub method."""
        return None

    async def wait_for_terminal_exit(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> WaitForTerminalExitResponse:
        """Stub method."""
        raise NotImplementedError("Not used in these tests")

    async def kill_terminal(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> KillTerminalCommandResponse | None:
        """Stub method."""
        return None

    def on_connect(self, conn: Any) -> None:
        """Stub method (sync, not async)."""
        pass

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Stub method."""
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Stub method."""
        pass


class MockActionObject:
    """Mock action object with visualize attribute."""

    def __init__(self, text: str):
        """Initialize mock action object."""
        self.visualize = text


class MockAction:
    """Mock action for testing.

    This provides the minimal interface used by ask_user_confirmation_acp:
    - tool_name: str
    - action: object with visualize attribute (or None)

    We use # type: ignore because ActionEvent is a complex Pydantic model with many
    required fields that are not used by the confirmation function. Creating full
    ActionEvent instances would require initializing many unused fields.
    """

    def __init__(self, tool_name: str = "unknown", action: str = ""):
        """Initialize mock action."""
        self.tool_name = tool_name
        self.action = MockActionObject(action) if action else None

    def to_dict(self):
        """Convert to dict."""
        return {"tool_name": self.tool_name, "action": self.action}


class TestAskUserConfirmationACP:
    """Test the ACP confirmation function."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "user_choice,expected_decision,expected_policy,additional_checks",
        [
            (
                "accept",
                UserConfirmation.ACCEPT,
                None,
                lambda result, mock_conn: (
                    mock_conn.last_request is not None
                    and mock_conn.last_request["session_id"] == "test-session"
                    and len(mock_conn.last_request["options"]) >= 2
                ),
            ),
            (
                "reject",
                UserConfirmation.REJECT,
                None,
                lambda result, mock_conn: (
                    result.reason is not None and "User rejected" in result.reason
                ),
            ),
            (
                "always_proceed",
                UserConfirmation.ACCEPT,
                "NeverConfirm",
                lambda result, mock_conn: result.policy_change is not None,
            ),
            (
                "risk_based",
                UserConfirmation.ACCEPT,
                "ConfirmRisky",
                lambda result, mock_conn: (
                    result.policy_change is not None
                    and result.policy_change.threshold.name == "HIGH"
                ),
            ),
        ],
        ids=["accept", "reject", "always_proceed", "risk_based"],
    )
    async def test_user_choices(
        self, user_choice, expected_decision, expected_policy, additional_checks
    ):
        """Test different user choice options for confirmation.

        Args:
            user_choice: The user's choice (accept, reject, always_proceed, risk_based)
            expected_decision: The expected UserConfirmation decision
            expected_policy: The expected policy change class name (or None)
            additional_checks: Lambda function for additional assertions
        """
        from openhands.sdk.security.confirmation_policy import (
            ConfirmRisky,
            NeverConfirm,
        )

        mock_conn = MockACPConnection(user_choice=user_choice)
        action = MockAction(tool_name="execute_bash", action="ls -la")

        result = await ask_user_confirmation_acp(
            conn=mock_conn,
            session_id="test-session",
            pending_actions=[action],  # type: ignore[arg-type]
        )

        assert result.decision == expected_decision

        if expected_policy:
            assert result.policy_change is not None
            if expected_policy == "NeverConfirm":
                assert isinstance(result.policy_change, NeverConfirm)
            elif expected_policy == "ConfirmRisky":
                assert isinstance(result.policy_change, ConfirmRisky)

        assert additional_checks(result, mock_conn)

    @pytest.mark.asyncio
    async def test_denied_outcome(self):
        """Test handling of DeniedOutcome (user cancelled)."""
        mock_conn = MockACPConnection(should_deny=True)
        action = MockAction(tool_name="execute_bash", action="ls")

        result = await ask_user_confirmation_acp(
            conn=mock_conn,
            session_id="test-session",
            pending_actions=[action],  # type: ignore[arg-type]
        )

        assert result.decision == UserConfirmation.REJECT
        assert result.reason is not None
        assert "User cancelled" in result.reason

    @pytest.mark.asyncio
    async def test_unknown_option_id(self):
        """Test handling of unknown option ID."""
        mock_conn = MockACPConnection(user_choice="unknown_option")
        action = MockAction(tool_name="execute_bash", action="ls")

        result = await ask_user_confirmation_acp(
            conn=mock_conn,
            session_id="test-session",
            pending_actions=[action],  # type: ignore[arg-type]
        )

        # Unknown options should be treated as reject
        assert result.decision == UserConfirmation.REJECT

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test handling of connection failures."""
        mock_conn = MockACPConnection(fail=True)
        action = MockAction(tool_name="execute_bash", action="ls")

        result = await ask_user_confirmation_acp(
            conn=mock_conn,
            session_id="test-session",
            pending_actions=[action],  # type: ignore[arg-type]
        )

        # Should defer on error rather than accepting or rejecting
        assert result.decision == UserConfirmation.DEFER

    @pytest.mark.asyncio
    async def test_multiple_actions(self):
        """Test confirmation with multiple actions."""
        mock_conn = MockACPConnection(user_choice="accept")
        actions = [
            MockAction(tool_name="execute_bash", action="ls"),
            MockAction(tool_name="str_replace_editor", action="view /tmp/file"),
            MockAction(tool_name="execute_bash", action="pwd"),
        ]

        result = await ask_user_confirmation_acp(
            conn=mock_conn,
            session_id="test-session",
            pending_actions=actions,  # type: ignore[arg-type]
        )

        assert result.decision == UserConfirmation.ACCEPT
        assert mock_conn.last_request is not None

    @pytest.mark.asyncio
    async def test_empty_actions(self):
        """Test confirmation with no actions."""
        mock_conn = MockACPConnection(user_choice="accept")

        result = await ask_user_confirmation_acp(
            conn=mock_conn,
            session_id="test-session",
            pending_actions=[],  # type: ignore[arg-type]
        )

        # Should auto-accept if no actions
        assert result.decision == UserConfirmation.ACCEPT

    @pytest.mark.asyncio
    async def test_action_with_none_action_object(self):
        """Test confirmation with action that has None action object."""
        mock_conn = MockACPConnection(user_choice="accept")
        action = MockAction(tool_name="some_tool", action="")  # Empty action

        result = await ask_user_confirmation_acp(
            conn=mock_conn,
            session_id="test-session",
            pending_actions=[action],  # type: ignore[arg-type]
        )

        assert result.decision == UserConfirmation.ACCEPT


class TestConfirmationOptions:
    """Test the permission options structure."""

    def test_permission_options_count(self):
        """Test that we have all expected permission options."""
        assert len(PERMISSION_OPTIONS) == 4

    def test_permission_options_ids(self):
        """Test that all expected option IDs are present."""
        option_ids = {opt.option_id for opt in PERMISSION_OPTIONS}
        assert option_ids == {"accept", "reject", "always_proceed", "risk_based"}

    def test_permission_options_kinds(self):
        """Test that permission options have correct kinds."""
        options_by_id = {opt.option_id: opt for opt in PERMISSION_OPTIONS}

        assert options_by_id["accept"].kind == "allow_once"
        assert options_by_id["reject"].kind == "reject_once"
        assert options_by_id["always_proceed"].kind == "allow_always"
        assert options_by_id["risk_based"].kind == "allow_once"

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
