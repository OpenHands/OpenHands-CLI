"""Tests for resuming conversations with different LLM settings."""

import json
import tempfile
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from openhands.sdk import LLM, Agent, Conversation, LLMSummarizingCondenser, Workspace
from openhands.sdk.conversation.persistence_const import BASE_STATE
from openhands.sdk.io import LocalFileStore
from openhands.sdk.security.confirmation_policy import NeverConfirm
from openhands_cli.setup import setup_conversation


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    with (
        tempfile.TemporaryDirectory() as work_dir,
        tempfile.TemporaryDirectory() as conv_dir,
    ):
        yield work_dir, conv_dir


def test_resume_conversation_with_different_enable_encrypted_reasoning(temp_dirs):
    """Test resuming a conversation when enable_encrypted_reasoning differs."""
    work_dir, conv_dir = temp_dirs
    conversation_id = UUID("12345678-1234-5678-1234-567812345678")

    # Create initial agent with enable_encrypted_reasoning=True
    initial_agent = Agent(
        llm=LLM(
            model="litellm_proxy/prod/claude-sonnet-4-5-20250929",
            api_key="test-key",
            enable_encrypted_reasoning=True,
        ),
        tools=[],
    )

    # Manually create persisted state with the initial agent
    conv_state_dir = Path(conv_dir) / conversation_id.hex
    conv_state_dir.mkdir(parents=True, exist_ok=True)

    state_data = {
        "id": str(conversation_id),
        "agent": initial_agent.model_dump(context={"expose_secrets": True}),
        "workspace": {"kind": "LocalWorkspace", "working_dir": work_dir},
        "persistence_dir": str(conv_state_dir),
        "max_iterations": 500,
        "stuck_detection": True,
    }

    file_store = LocalFileStore(str(conv_state_dir))
    file_store.write(BASE_STATE, json.dumps(state_data))

    # Now try to resume with enable_encrypted_reasoning=False and different model
    resume_agent = Agent(
        llm=LLM(
            model="litellm_proxy/claude-sonnet-4-5-20250929",  # Different model prefix
            api_key="test-key",
            enable_encrypted_reasoning=False,  # Different setting
        ),
        tools=[],
    )

    # This should raise ValueError due to mismatched settings
    with pytest.raises(ValueError) as exc_info:
        Conversation(
            agent=resume_agent,
            workspace=Workspace(working_dir=work_dir),
            persistence_dir=conv_dir,
            conversation_id=conversation_id,
        )

    # Verify the error message mentions the differences
    error_message = str(exc_info.value)
    assert "enable_encrypted_reasoning" in error_message
    assert "model" in error_message


def test_resume_conversation_with_different_model_name(temp_dirs):
    """Test resuming a conversation when model name differs."""
    work_dir, conv_dir = temp_dirs
    conversation_id = UUID("12345678-1234-5678-1234-567812345678")

    # Create initial agent
    initial_agent = Agent(
        llm=LLM(
            model="litellm_proxy/prod/claude-sonnet-4-5-20250929",
            api_key="test-key",
        ),
        tools=[],
    )

    # Manually create persisted state
    conv_state_dir = Path(conv_dir) / conversation_id.hex
    conv_state_dir.mkdir(parents=True, exist_ok=True)

    state_data = {
        "id": str(conversation_id),
        "agent": initial_agent.model_dump(context={"expose_secrets": True}),
        "workspace": {"kind": "LocalWorkspace", "working_dir": work_dir},
        "persistence_dir": str(conv_state_dir),
        "max_iterations": 500,
        "stuck_detection": True,
    }

    file_store = LocalFileStore(str(conv_state_dir))
    file_store.write(BASE_STATE, json.dumps(state_data))

    # Try to resume with different model name
    resume_agent = Agent(
        llm=LLM(
            model="litellm_proxy/claude-sonnet-4-5-20250929",  # Different prefix
            api_key="test-key",
        ),
        tools=[],
    )

    # This should raise ValueError due to mismatched model
    with pytest.raises(ValueError) as exc_info:
        Conversation(
            agent=resume_agent,
            workspace=Workspace(working_dir=work_dir),
            persistence_dir=conv_dir,
            conversation_id=conversation_id,
        )

    # Verify the error message mentions the model difference
    error_message = str(exc_info.value)
    assert "model" in error_message


def test_resume_conversation_with_same_settings(temp_dirs):
    """Test resuming a conversation with same settings should work."""
    work_dir, conv_dir = temp_dirs
    conversation_id = UUID("12345678-1234-5678-1234-567812345678")

    # Create initial agent
    initial_agent = Agent(
        llm=LLM(
            model="litellm_proxy/claude-sonnet-4-5-20250929",
            api_key="test-key",
        ),
        tools=[],
    )

    # Manually create persisted state
    conv_state_dir = Path(conv_dir) / conversation_id.hex
    conv_state_dir.mkdir(parents=True, exist_ok=True)

    state_data = {
        "id": str(conversation_id),
        "agent": initial_agent.model_dump(context={"expose_secrets": True}),
        "workspace": {"kind": "LocalWorkspace", "working_dir": work_dir},
        "persistence_dir": str(conv_state_dir),
        "max_iterations": 500,
        "stuck_detection": True,
    }

    file_store = LocalFileStore(str(conv_state_dir))
    file_store.write(BASE_STATE, json.dumps(state_data))

    # Try to resume with same settings (but possibly updated API key)
    resume_agent = Agent(
        llm=LLM(
            model="litellm_proxy/claude-sonnet-4-5-20250929",
            api_key="new-test-key",  # API keys can differ (in OVERRIDE_ON_SERIALIZE)
        ),
        tools=[],
    )

    # This should work fine
    resumed_conversation = Conversation(
        agent=resume_agent,
        workspace=Workspace(working_dir=work_dir),
        persistence_dir=conv_dir,
        conversation_id=conversation_id,
    )

    # Verify the conversation was resumed
    assert resumed_conversation is not None
    assert resumed_conversation.id == conversation_id


def test_setup_conversation_resumes_with_different_settings(temp_dirs):
    """
    Test that setup_conversation properly handles resuming with different
    settings.
    """
    work_dir, conv_dir = temp_dirs
    conversation_id = UUID("12345678-1234-5678-1234-567812345678")

    # Create initial agent with enable_encrypted_reasoning=True
    initial_agent = Agent(
        llm=LLM(
            model="litellm_proxy/prod/claude-sonnet-4-5-20250929",
            api_key="test-key",
            enable_encrypted_reasoning=True,
        ),
        tools=[],
    )

    # Manually create persisted state
    conv_state_dir = Path(conv_dir) / conversation_id.hex
    conv_state_dir.mkdir(parents=True, exist_ok=True)

    state_data = {
        "id": str(conversation_id),
        "agent": initial_agent.model_dump(context={"expose_secrets": True}),
        "workspace": {"kind": "LocalWorkspace", "working_dir": work_dir},
        "persistence_dir": str(conv_state_dir),
        "max_iterations": 500,
        "stuck_detection": True,
    }

    file_store = LocalFileStore(str(conv_state_dir))
    file_store.write(BASE_STATE, json.dumps(state_data))

    # Now try to resume with different settings using setup_conversation
    resume_agent = Agent(
        llm=LLM(
            model="litellm_proxy/claude-sonnet-4-5-20250929",  # Different model prefix
            api_key="new-test-key",
            enable_encrypted_reasoning=False,  # Different setting
        ),
        tools=[],
    )

    # Mock the AgentStore to return the resume_agent with different settings
    with patch("openhands_cli.setup.AgentStore") as mock_store_class:
        mock_store = MagicMock()
        mock_store.load.return_value = resume_agent
        mock_store_class.return_value = mock_store

        # Mock the locations
        with (
            patch("openhands_cli.setup.WORK_DIR", work_dir),
            patch("openhands_cli.setup.CONVERSATIONS_DIR", conv_dir),
        ):
            # This should now work with our fix - it should use the persisted settings
            resumed_conversation = cast(
                Conversation,
                setup_conversation(
                    conversation_id=conversation_id,
                    confirmation_policy=NeverConfirm(),
                ),
            )

        # Verify the conversation was resumed
        assert resumed_conversation is not None
        assert resumed_conversation.id == conversation_id  # type: ignore[reportAttributeAccessIssue]

        # Verify that the resumed conversation uses the PERSISTED agent's model settings
        # not the current settings from AgentStore
        assert (
            resumed_conversation.agent.llm.model  # type: ignore[reportAttributeAccessIssue]
            == "litellm_proxy/prod/claude-sonnet-4-5-20250929"
        )
        assert resumed_conversation.agent.llm.enable_encrypted_reasoning is True  # type: ignore[reportAttributeAccessIssue]

        # But the API key should be updated from the current agent
        assert (
            resumed_conversation.agent.llm.api_key.get_secret_value() == "new-test-key"  # type: ignore[reportAttributeAccessIssue]
        )


def test_setup_conversation_resumes_with_condenser(temp_dirs):
    """Test that setup_conversation properly handles resuming with condenser LLM."""
    work_dir, conv_dir = temp_dirs
    conversation_id = UUID("12345678-1234-5678-1234-567812345678")

    # Create initial agent with condenser
    initial_agent = Agent(
        llm=LLM(
            model="litellm_proxy/prod/claude-sonnet-4-5-20250929",
            api_key="test-key",
            usage_id="agent",
        ),
        condenser=LLMSummarizingCondenser(
            llm=LLM(
                model="litellm_proxy/prod/claude-sonnet-4-5-20250929",
                api_key="test-key",
                usage_id="condenser",
            )
        ),
        tools=[],
    )

    # Manually create persisted state
    conv_state_dir = Path(conv_dir) / conversation_id.hex
    conv_state_dir.mkdir(parents=True, exist_ok=True)

    state_data = {
        "id": str(conversation_id),
        "agent": initial_agent.model_dump(context={"expose_secrets": True}),
        "workspace": {"kind": "LocalWorkspace", "working_dir": work_dir},
        "persistence_dir": str(conv_state_dir),
        "max_iterations": 500,
        "stuck_detection": True,
    }

    file_store = LocalFileStore(str(conv_state_dir))
    file_store.write(BASE_STATE, json.dumps(state_data))

    # Try to resume with different settings
    resume_agent = Agent(
        llm=LLM(
            model="litellm_proxy/claude-sonnet-4-5-20250929",  # Different prefix
            api_key="new-test-key",
            usage_id="agent",
        ),
        condenser=LLMSummarizingCondenser(
            llm=LLM(
                model="litellm_proxy/claude-sonnet-4-5-20250929",
                api_key="new-test-key",
                usage_id="condenser",
            )
        ),
        tools=[],
    )

    # Mock the AgentStore
    with patch("openhands_cli.setup.AgentStore") as mock_store_class:
        mock_store = MagicMock()
        mock_store.load.return_value = resume_agent
        mock_store_class.return_value = mock_store

        # Mock the locations
        with (
            patch("openhands_cli.setup.WORK_DIR", work_dir),
            patch("openhands_cli.setup.CONVERSATIONS_DIR", conv_dir),
        ):
            resumed_conversation = cast(
                Conversation,
                setup_conversation(
                    conversation_id=conversation_id,
                    confirmation_policy=NeverConfirm(),
                ),
            )

        # Verify the conversation was resumed
        assert resumed_conversation is not None
        assert resumed_conversation.id == conversation_id  # type: ignore[reportAttributeAccessIssue]

        # Verify that both agent and condenser use persisted model
        assert (
            resumed_conversation.agent.llm.model  # type: ignore[reportAttributeAccessIssue]
            == "litellm_proxy/prod/claude-sonnet-4-5-20250929"
        )
        assert (
            resumed_conversation.agent.condenser.llm.model  # type: ignore[reportAttributeAccessIssue]
            == "litellm_proxy/prod/claude-sonnet-4-5-20250929"
        )

        # But the API keys should be updated
        assert (
            resumed_conversation.agent.llm.api_key.get_secret_value() == "new-test-key"  # type: ignore[reportAttributeAccessIssue]
        )
        assert (
            resumed_conversation.agent.condenser.llm.api_key.get_secret_value()  # type: ignore[reportAttributeAccessIssue]
            == "new-test-key"
        )
