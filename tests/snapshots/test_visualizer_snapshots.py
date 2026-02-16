"""Snapshot tests for the ConversationVisualizer widget.

These tests verify the visual appearance of action events, including
proper padding alignment with user messages.
"""

from typing import TYPE_CHECKING, Any, Literal, cast
from unittest.mock import MagicMock

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from openhands.sdk.event import ActionEvent, UserRejectObservation
from openhands.sdk.llm import MessageToolCall
from openhands.sdk.tool.builtins.finish import FinishAction
from openhands.sdk.tool.builtins.think import ThinkAction
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.panels.plan_side_panel import PlanSidePanel
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp


class VisualizerTestApp(App):
    """Test app for visualizer snapshots.

    Uses the same CSS styling as the real OpenHands CLI app to ensure
    accurate visual testing.
    """

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
    }
    #scroll_view {
        height: 100%;
        width: 100%;
        margin: 1 1 0 1;
        background: $background;
    }
    .user-message {
        padding: 0 1;
        margin-top: 1;
        margin-bottom: 1;
        background: $background;
        color: $primary;
    }
    """

    def __init__(self, events: list[Any]) -> None:
        super().__init__()
        self.events = events
        self.conversation_dir = ""
        self.register_theme(OPENHANDS_THEME)
        self.theme = "openhands"
        # Create a mock plan_panel that's not on screen
        self.plan_panel = MagicMock(spec=PlanSidePanel)
        self.plan_panel.is_on_screen = False
        self.plan_panel.user_dismissed = False

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="scroll_view"):
            # User message with same styling as real CLI
            yield Static("> hi how are you", classes="user-message")

    def on_mount(self) -> None:
        container = self.query_one("#scroll_view", VerticalScroll)
        # Cast to satisfy type checker - this is a test-only workaround
        self.visualizer = ConversationVisualizer(container, cast("OpenHandsApp", self))
        for event in self.events:
            self.visualizer.on_event(event)


def _create_finish_action_event(message: str) -> ActionEvent:
    """Create a FinishAction event for testing."""
    tool_call = MessageToolCall(
        id="test_finish_id",
        name="finish",
        arguments=f'{{"message": "{message}"}}',
        origin="responses",
    )
    return ActionEvent(
        source="agent",
        thought=[],
        reasoning_content=None,
        thinking_blocks=[],
        responses_reasoning_item=None,
        tool_call=tool_call,
        tool_name="finish",
        tool_call_id="test_finish_id",
        llm_response_id="test_response_id",
        action=FinishAction(message=message),
        summary="Finish the task",
    )


def _create_think_action_event(thought: str) -> ActionEvent:
    """Create a ThinkAction event for testing."""
    tool_call = MessageToolCall(
        id="test_think_id",
        name="think",
        arguments=f'{{"thought": "{thought}"}}',
        origin="responses",
    )
    return ActionEvent(
        source="agent",
        thought=[],
        reasoning_content=None,
        thinking_blocks=[],
        responses_reasoning_item=None,
        tool_call=tool_call,
        tool_name="think",
        tool_call_id="test_think_id",
        llm_response_id="test_response_id",
        action=ThinkAction(thought=thought),
        summary="Think about the problem",
    )


def _create_user_reject_observation(
    rejection_reason: str,
    rejection_source: Literal["user", "hook"] = "user",
) -> UserRejectObservation:
    """Create a UserRejectObservation event for testing."""
    return UserRejectObservation(
        action_id="test_action_id",
        tool_name="terminal",
        tool_call_id="test_tool_call_id",
        rejection_reason=rejection_reason,
        rejection_source=rejection_source,
    )


class TestVisualizerSnapshots:
    """Snapshot tests for the ConversationVisualizer."""

    def test_finish_action_padding(self, snap_compare):
        """Verify finish action has proper left padding to align with user message."""
        events = [_create_finish_action_event("Task completed successfully!")]
        assert snap_compare(VisualizerTestApp(events), terminal_size=(80, 12))

    def test_think_action_padding(self, snap_compare):
        """Verify think action has proper left padding to align with user message."""
        events = [_create_think_action_event("Let me analyze this problem...")]
        assert snap_compare(VisualizerTestApp(events), terminal_size=(80, 12))

    def test_multiple_actions_alignment(self, snap_compare):
        """Verify multiple actions maintain consistent alignment."""
        events = [
            _create_think_action_event("First, let me think about this..."),
            _create_finish_action_event("Done! Here's the result."),
        ]
        assert snap_compare(VisualizerTestApp(events), terminal_size=(80, 16))


class TestRejectionEventSnapshots:
    """Snapshot tests for rejection events (user and hook rejections)."""

    def test_user_rejection_display(self, snap_compare):
        """Verify user rejection shows 'User Rejected Action' title."""
        events = [
            _create_user_reject_observation(
                rejection_reason="I don't want to run this command",
                rejection_source="user",
            )
        ]
        assert snap_compare(VisualizerTestApp(events), terminal_size=(80, 12))

    def test_hook_rejection_display(self, snap_compare):
        """Verify hook rejection shows 'Hook Blocked Action' title with ⚡ icon."""
        events = [
            _create_user_reject_observation(
                rejection_reason="Blocked by security hook: dangerous command detected",
                rejection_source="hook",
            )
        ]
        assert snap_compare(VisualizerTestApp(events), terminal_size=(80, 12))

    def test_user_and_hook_rejections_comparison(self, snap_compare):
        """Verify visual difference between user and hook rejections."""
        events = [
            _create_user_reject_observation(
                rejection_reason="User chose not to proceed",
                rejection_source="user",
            ),
            _create_user_reject_observation(
                rejection_reason="Hook blocked: rm -rf detected",
                rejection_source="hook",
            ),
        ]
        assert snap_compare(VisualizerTestApp(events), terminal_size=(80, 16))
