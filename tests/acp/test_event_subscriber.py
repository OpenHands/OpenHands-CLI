"""Tests for the EventSubscriber class."""

from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest
from acp import SessionNotification
from acp.schema import (
    SessionUpdate2,
    SessionUpdate3,
    SessionUpdate4,
    SessionUpdate5,
    SessionUpdate6,
)

from openhands.sdk import Message, TextContent
from openhands.sdk.event import (
    AgentErrorEvent,
    Condensation,
    CondensationRequest,
    ConversationStateUpdateEvent,
    MessageEvent,
    ObservationEvent,
    PauseEvent,
    SystemPromptEvent,
)
from openhands.tools.task_tracker.definition import (
    TaskItem,
    TaskTrackerObservation,
)
from openhands_cli.acp_impl.event import EventSubscriber


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def event_subscriber(mock_connection):
    """Create an EventSubscriber instance."""
    return EventSubscriber("test-session", mock_connection)


@pytest.mark.asyncio
async def test_handle_message_event(event_subscriber, mock_connection):
    """Test handling of MessageEvent from assistant."""
    # Create a mock MessageEvent
    message = Message(role="assistant", content=[TextContent(text="Test response")])
    event = MessageEvent(source="agent", llm_message=message)

    # Process the event
    await event_subscriber(event)

    # Verify sessionUpdate was called
    assert mock_connection.sessionUpdate.called
    call_args = mock_connection.sessionUpdate.call_args[0][0]
    assert isinstance(call_args, SessionNotification)
    assert call_args.session_id == "test-session"
    assert isinstance(call_args.update, SessionUpdate2)
    assert call_args.update.session_update == "agent_message_chunk"


@pytest.mark.asyncio
async def test_handle_action_event(event_subscriber, mock_connection):
    """Test handling of ActionEvent."""
    # Create a mock ActionEvent with proper structure
    from rich.text import Text

    # Create a simple object for the action with only needed attributes
    class MockAction:
        title = "Test Action"
        visualize = Text("Executing test action")

        def model_dump(self):
            return {"title": self.title}

    # Create a simple object for tool_call
    class MockToolCall:
        class MockFunction:
            arguments = '{"arg": "value"}'

        function = MockFunction()

    # Create event (use a simple object to avoid MagicMock's hasattr behavior)
    class MockEvent:
        thought: ClassVar[list[TextContent]] = [
            TextContent(text="Thinking about the task")
        ]
        reasoning_content = "This is my reasoning"
        tool_name = "terminal"
        tool_call_id = "test-call-123"
        action = MockAction()
        tool_call = MockToolCall()
        visualize = Text("Executing test action")

    event = MockEvent()

    # Process the event
    await event_subscriber._handle_action_event(event)

    # Verify sessionUpdate was called multiple times (reasoning, thought, tool_call)
    # Should be at least 2: thought + tool_call
    assert mock_connection.sessionUpdate.call_count >= 2

    # Check that tool_call notification was sent
    calls = mock_connection.sessionUpdate.call_args_list
    tool_call_found = False
    for call in calls:
        notification = call[0][0]
        if isinstance(notification.update, SessionUpdate4):
            tool_call_found = True
            assert notification.update.session_update == "tool_call"
            assert notification.update.tool_call_id == "test-call-123"
            assert notification.update.kind == "execute"  # terminal maps to execute
            assert notification.update.status == "in_progress"

    assert tool_call_found, "tool_call notification should be sent"


@pytest.mark.asyncio
async def test_handle_observation_event(event_subscriber, mock_connection):
    """Test handling of ObservationEvent."""
    from rich.text import Text

    # Create a mock observation
    mock_observation = MagicMock()
    mock_observation.to_llm_content = [
        TextContent(text="Command executed successfully")
    ]

    # Create ObservationEvent
    event = MagicMock(spec=ObservationEvent)
    event.visualize = Text("Result: success")
    event.tool_call_id = "test-call-123"
    event.observation = mock_observation

    # Process the event
    await event_subscriber._handle_observation_event(event)

    # Verify sessionUpdate was called
    assert mock_connection.sessionUpdate.called
    call_args = mock_connection.sessionUpdate.call_args[0][0]
    assert isinstance(call_args, SessionNotification)
    assert isinstance(call_args.update, SessionUpdate5)
    assert call_args.update.session_update == "tool_call_update"
    assert call_args.update.toolCallId == "test-call-123"
    assert call_args.update.status == "completed"


@pytest.mark.asyncio
async def test_handle_agent_error_event(event_subscriber, mock_connection):
    """Test handling of AgentErrorEvent."""
    from rich.text import Text

    # Create AgentErrorEvent
    event = MagicMock(spec=AgentErrorEvent)
    event.visualize = Text("Error: Something went wrong")
    event.tool_call_id = "test-call-123"
    event.error = "Something went wrong"
    event.model_dump = MagicMock(return_value={"error": "Something went wrong"})

    # Process the event
    await event_subscriber._handle_observation_event(event)

    # Verify sessionUpdate was called
    assert mock_connection.sessionUpdate.called
    call_args = mock_connection.sessionUpdate.call_args[0][0]
    assert isinstance(call_args, SessionNotification)
    assert isinstance(call_args.update, SessionUpdate5)
    assert call_args.update.session_update == "tool_call_update"
    assert call_args.update.status == "failed"
    assert call_args.update.rawOutput == {"error": "Something went wrong"}


@pytest.mark.asyncio
async def test_event_subscriber_with_empty_text(event_subscriber, mock_connection):
    """Test that events with empty text don't trigger updates."""
    # Create a MessageEvent with empty text
    message = Message(role="assistant", content=[TextContent(text="")])
    event = MessageEvent(source="agent", llm_message=message)

    # Process the event
    await event_subscriber(event)

    # Verify sessionUpdate was not called for empty text
    assert not mock_connection.sessionUpdate.called


@pytest.mark.asyncio
async def test_event_subscriber_with_user_message(event_subscriber, mock_connection):
    """Test that user messages are NOT sent (to avoid duplication in Zed UI)."""
    # Create a MessageEvent from user (not agent)
    message = Message(role="user", content=[TextContent(text="User message")])
    event = MessageEvent(source="user", llm_message=message)

    # Process the event
    await event_subscriber(event)

    # Verify sessionUpdate was NOT called (user messages are skipped)
    # NOTE: Zed UI renders user messages when they're sent, so we don't
    # want to duplicate them by sending them again as UserMessageChunk
    assert not mock_connection.sessionUpdate.called


@pytest.mark.asyncio
async def test_handle_system_prompt_event(event_subscriber, mock_connection):
    """Test handling of SystemPromptEvent."""
    # Create a SystemPromptEvent
    event = SystemPromptEvent(
        source="agent", system_prompt=TextContent(text="System prompt"), tools=[]
    )

    # Process the event
    await event_subscriber(event)

    # Verify sessionUpdate was called
    assert mock_connection.sessionUpdate.called
    call_args = mock_connection.sessionUpdate.call_args[0][0]
    assert isinstance(call_args, SessionNotification)
    assert call_args.session_id == "test-session"
    assert isinstance(call_args.update, SessionUpdate3)
    assert call_args.update.session_update == "agent_thought_chunk"


@pytest.mark.asyncio
async def test_handle_pause_event(event_subscriber, mock_connection):
    """Test handling of PauseEvent."""
    # Create a PauseEvent
    event = PauseEvent(source="user")

    # Process the event
    await event_subscriber(event)

    # Verify sessionUpdate was called
    assert mock_connection.sessionUpdate.called
    call_args = mock_connection.sessionUpdate.call_args[0][0]
    assert isinstance(call_args, SessionNotification)
    assert call_args.session_id == "test-session"
    assert isinstance(call_args.update, SessionUpdate3)
    assert call_args.update.session_update == "agent_thought_chunk"


@pytest.mark.asyncio
async def test_handle_condensation_event(event_subscriber, mock_connection):
    """Test handling of Condensation event."""
    # Create a Condensation event
    event = Condensation(
        source="environment",
        forgotten_event_ids=["event1", "event2"],
        summary="Some events were forgotten",
        llm_response_id="response-123",
    )

    # Process the event
    await event_subscriber(event)

    # Verify sessionUpdate was called
    assert mock_connection.sessionUpdate.called
    call_args = mock_connection.sessionUpdate.call_args[0][0]
    assert isinstance(call_args, SessionNotification)
    assert call_args.session_id == "test-session"
    assert isinstance(call_args.update, SessionUpdate3)
    assert call_args.update.session_update == "agent_thought_chunk"


@pytest.mark.asyncio
async def test_handle_condensation_request_event(event_subscriber, mock_connection):
    """Test handling of CondensationRequest event."""
    # Create a CondensationRequest event
    event = CondensationRequest(source="environment")

    # Process the event
    await event_subscriber(event)

    # Verify sessionUpdate was called
    assert mock_connection.sessionUpdate.called
    call_args = mock_connection.sessionUpdate.call_args[0][0]
    assert isinstance(call_args, SessionNotification)
    assert call_args.session_id == "test-session"
    assert isinstance(call_args.update, SessionUpdate3)
    assert call_args.update.session_update == "agent_thought_chunk"


@pytest.mark.asyncio
async def test_conversation_state_update_event_is_skipped(
    event_subscriber, mock_connection
):
    """Test that ConversationStateUpdateEvent is skipped."""
    # Create a ConversationStateUpdateEvent
    event = ConversationStateUpdateEvent(source="environment", key="test", value="test")

    # Process the event
    await event_subscriber(event)

    # Verify sessionUpdate was NOT called
    assert not mock_connection.sessionUpdate.called


@pytest.mark.asyncio
async def test_handle_task_tracker_observation(event_subscriber, mock_connection):
    """Test handling of TaskTrackerObservation with plan updates."""
    # Create a TaskTrackerObservation with multiple tasks
    task_list = [
        TaskItem(title="Task 1", notes="Details for task 1", status="done"),
        TaskItem(title="Task 2", notes="", status="in_progress"),
        TaskItem(title="Task 3", notes="Details for task 3", status="todo"),
    ]

    observation = TaskTrackerObservation.from_text(
        text="Task list updated",
        command="plan",
        task_list=task_list,
    )

    # Create an ObservationEvent wrapping the TaskTrackerObservation
    event = MagicMock(spec=ObservationEvent)
    event.observation = observation
    event.tool_call_id = "task-call-123"
    event.model_dump = MagicMock(return_value={"command": "plan"})

    # Process the event
    await event_subscriber._handle_observation_event(event)

    # Verify sessionUpdate was called twice (plan + tool_call_update)
    assert mock_connection.sessionUpdate.call_count == 2

    # Verify the plan update was sent
    calls = mock_connection.sessionUpdate.call_args_list
    plan_update_found = False
    tool_call_update_found = False

    for call in calls:
        notification = call[0][0]
        if isinstance(notification.update, SessionUpdate6):
            plan_update_found = True
            # Verify plan structure
            assert notification.update.session_update == "plan"
            assert len(notification.update.entries) == 3

            # Verify first entry (done -> completed)
            # Note: notes are intentionally omitted for conciseness
            entry1 = notification.update.entries[0]
            assert entry1.content == "Task 1"
            assert entry1.status == "completed"
            assert entry1.priority == "medium"

            # Verify second entry (in_progress -> in_progress)
            entry2 = notification.update.entries[1]
            assert entry2.content == "Task 2"
            assert entry2.status == "in_progress"
            assert entry2.priority == "medium"

            # Verify third entry (todo -> pending)
            entry3 = notification.update.entries[2]
            assert entry3.content == "Task 3"
            assert entry3.status == "pending"
            assert entry3.priority == "medium"

        elif isinstance(notification.update, SessionUpdate5):
            tool_call_update_found = True
            assert notification.update.session_update == "tool_call_update"
            assert notification.update.tool_call_id == "task-call-123"
            assert notification.update.status == "completed"

    assert plan_update_found, "AgentPlanUpdate notification should be sent"
    assert tool_call_update_found, "ToolCallProgress notification should be sent"


@pytest.mark.asyncio
async def test_handle_task_tracker_with_empty_list(event_subscriber, mock_connection):
    """Test handling of TaskTrackerObservation with empty task list."""
    observation = TaskTrackerObservation.from_text(
        text="No tasks",
        command="view",
        task_list=[],
    )

    event = MagicMock(spec=ObservationEvent)
    event.observation = observation
    event.tool_call_id = "task-call-456"
    event.model_dump = MagicMock(return_value={"command": "view"})

    # Process the event
    await event_subscriber._handle_observation_event(event)

    # Verify sessionUpdate was called twice (plan with empty list + tool_call_update)
    assert mock_connection.sessionUpdate.call_count == 2

    # Verify empty plan was sent
    calls = mock_connection.sessionUpdate.call_args_list
    plan_found = False
    for call in calls:
        notification = call[0][0]
        if isinstance(notification.update, SessionUpdate6):
            plan_found = True
            assert notification.update.entries == []

    assert plan_found, "AgentPlanUpdate with empty entries should be sent"


@pytest.mark.asyncio
async def test_get_metadata_with_status_line(mock_connection):
    """Test that _get_metadata returns status_line along with raw metrics."""
    from unittest.mock import Mock

    # Create a mock conversation with stats
    mock_conversation = Mock()

    # Create mock token usage
    usage = Mock()
    usage.prompt_tokens = 1234
    usage.completion_tokens = 567
    usage.cache_read_tokens = 123
    usage.reasoning_tokens = 100

    # Create mock metrics
    metrics = Mock()
    metrics.accumulated_cost = 0.0567
    metrics.accumulated_token_usage = usage

    # Set up the mock to return our metrics
    mock_conversation.conversation_stats.get_combined_metrics.return_value = metrics

    # Create EventSubscriber with conversation
    event_subscriber = EventSubscriber(
        "test-session", mock_connection, mock_conversation
    )

    # Get metadata
    metadata = event_subscriber._get_metadata()

    # Verify metadata structure
    assert metadata is not None
    assert "openhands.dev/metrics" in metadata
    metrics_dict = metadata["openhands.dev/metrics"]

    # Verify raw metrics
    assert metrics_dict["input_tokens"] == 1234
    assert metrics_dict["output_tokens"] == 567
    assert metrics_dict["cache_read_tokens"] == 123
    assert metrics_dict["reasoning_tokens"] == 100
    assert metrics_dict["cost"] == 0.0567

    # Verify status_line is present and formatted correctly
    assert "status_line" in metrics_dict
    status_line = metrics_dict["status_line"]
    assert isinstance(status_line, str)
    # Should contain key components
    assert "↑ input" in status_line
    assert "↓ output" in status_line
    assert "cache hit" in status_line
    assert "reasoning" in status_line  # Since reasoning_tokens > 0
    assert "$" in status_line
    # Check abbreviated values
    assert "1.23K" in status_line  # input_tokens abbreviated
    assert "567" in status_line  # output_tokens not abbreviated (< 1000)


@pytest.mark.asyncio
async def test_format_status_line_abbreviations(mock_connection):
    """Test that _format_status_line correctly abbreviates large numbers."""
    from unittest.mock import Mock

    # Create a mock conversation with large token counts
    mock_conversation = Mock()

    # Create token usage with large numbers
    usage = Mock()
    usage.prompt_tokens = 5_234_567  # Should be 5.23M
    usage.completion_tokens = 1_234_567  # Should be 1.23M
    usage.cache_read_tokens = 2_617_284  # cache hit rate: 50%
    usage.reasoning_tokens = 0

    metrics = Mock()
    metrics.accumulated_cost = 12.3456
    metrics.accumulated_token_usage = usage

    mock_conversation.conversation_stats.get_combined_metrics.return_value = metrics

    event_subscriber = EventSubscriber(
        "test-session", mock_connection, mock_conversation
    )

    # Get status line
    metadata = event_subscriber._get_metadata()
    assert metadata is not None
    status_line = metadata["openhands.dev/metrics"]["status_line"]
    assert isinstance(status_line, str)

    # Verify abbreviations
    assert "5.23M" in status_line  # 5,234,567 abbreviated
    assert "1.23M" in status_line  # 1,234,567 abbreviated
    assert "50.00%" in status_line  # Cache hit rate
    assert "12.3456" in status_line  # Cost
