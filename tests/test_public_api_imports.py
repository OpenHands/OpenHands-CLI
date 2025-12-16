"""Test that we can import required classes from the public openhands.sdk API."""

import pytest


def test_public_api_imports():
    """Test that all required classes can be imported from openhands.sdk public API."""
    # Test that we can import all the classes we moved to public API
    from openhands.sdk import (
        Action,
        Agent,
        AgentContext,
        Conversation,
        ConversationExecutionStatus,
        Event,
        LLMSummarizingCondenser,
        LocalConversation,
        LocalFileStore,
        Message,
        MessageEvent,
        TextContent,
        Workspace,
    )

    # Verify that the classes are actually classes/types
    assert Action is not None
    assert Agent is not None
    assert AgentContext is not None
    assert Conversation is not None
    assert ConversationExecutionStatus is not None
    assert Event is not None
    assert LLMSummarizingCondenser is not None
    assert LocalConversation is not None
    assert LocalFileStore is not None
    assert Message is not None
    assert MessageEvent is not None
    assert TextContent is not None
    assert Workspace is not None


def test_conversation_execution_status_enum():
    """Test that ConversationExecutionStatus enum values are accessible."""
    from openhands.sdk import ConversationExecutionStatus

    # Test that we can access the enum values
    assert hasattr(ConversationExecutionStatus, 'RUNNING')
    assert hasattr(ConversationExecutionStatus, 'IDLE')
    assert hasattr(ConversationExecutionStatus, 'FINISHED')
    assert hasattr(ConversationExecutionStatus, 'ERROR')
    assert hasattr(ConversationExecutionStatus, 'PAUSED')
    assert hasattr(ConversationExecutionStatus, 'WAITING_FOR_CONFIRMATION')
    assert hasattr(ConversationExecutionStatus, 'STUCK')


def test_event_classes():
    """Test that Event and MessageEvent are accessible and usable."""
    from openhands.sdk import Event, MessageEvent, Message, TextContent

    # Test that we can create instances
    message = Message(role="user", content=[TextContent(text="test")])
    message_event = MessageEvent(source="user", llm_message=message)
    
    assert isinstance(message_event, Event)
    assert message_event.llm_message.role == "user"
    assert message_event.llm_message.content[0].text == "test"


def test_action_class():
    """Test that Action class is accessible."""
    from openhands.sdk import Action

    # Action is an abstract base class, so we just verify it exists
    assert Action is not None
    assert hasattr(Action, '__abstractmethods__')


def test_agent_context():
    """Test that AgentContext is accessible and can be instantiated."""
    from openhands.sdk import AgentContext

    # Test basic instantiation
    context = AgentContext()
    assert context is not None


def test_workspace_classes():
    """Test that Workspace classes are accessible."""
    from openhands.sdk import Workspace, LocalFileStore

    # Test that classes exist
    assert Workspace is not None
    assert LocalFileStore is not None


def test_llm_condenser():
    """Test that LLMSummarizingCondenser is accessible."""
    from openhands.sdk import LLMSummarizingCondenser

    assert LLMSummarizingCondenser is not None