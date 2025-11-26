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
    assert call_args.sessionId == "test-session"
    assert isinstance(call_args.update, SessionUpdate2)
    assert call_args.update.sessionUpdate == "agent_message_chunk"


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
            assert notification.update.sessionUpdate == "tool_call"
            assert notification.update.toolCallId == "test-call-123"
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
    assert call_args.update.sessionUpdate == "tool_call_update"
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
    assert call_args.update.sessionUpdate == "tool_call_update"
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
    assert call_args.sessionId == "test-session"
    assert isinstance(call_args.update, SessionUpdate3)
    assert call_args.update.sessionUpdate == "agent_thought_chunk"


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
    assert call_args.sessionId == "test-session"
    assert isinstance(call_args.update, SessionUpdate3)
    assert call_args.update.sessionUpdate == "agent_thought_chunk"


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
    assert call_args.sessionId == "test-session"
    assert isinstance(call_args.update, SessionUpdate3)
    assert call_args.update.sessionUpdate == "agent_thought_chunk"


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
    assert call_args.sessionId == "test-session"
    assert isinstance(call_args.update, SessionUpdate3)
    assert call_args.update.sessionUpdate == "agent_thought_chunk"


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
            assert notification.update.sessionUpdate == "plan"
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
            assert notification.update.sessionUpdate == "tool_call_update"
            assert notification.update.toolCallId == "task-call-123"
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
