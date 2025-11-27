"""Tests for the minimal conversation runner functionality."""

import unittest.mock as mock

import pytest

from openhands_cli.refactor.conversation_runner import MinimalConversationRunner


class TestMinimalConversationRunner:
    """Tests for the MinimalConversationRunner class."""

    def test_initialization(self):
        """Test that the conversation runner initializes correctly."""
        runner = MinimalConversationRunner()

        assert runner.conversation is None
        assert runner.conversation_id is None
        assert runner.is_running is False
        assert runner.visualizer is None

    def test_initialization_with_visualizer(self):
        """Test that the conversation runner initializes with visualizer."""
        mock_visualizer = mock.MagicMock()
        runner = MinimalConversationRunner(visualizer=mock_visualizer)

        assert runner.visualizer is mock_visualizer

    @mock.patch("openhands_cli.refactor.conversation_runner.setup_conversation")
    @mock.patch("uuid.uuid4")
    def test_initialize_conversation(self, mock_uuid, mock_setup):
        """Test conversation initialization."""
        mock_conversation_id = mock.MagicMock()
        mock_uuid.return_value = mock_conversation_id
        mock_conversation = mock.MagicMock()
        mock_setup.return_value = mock_conversation

        runner = MinimalConversationRunner()
        runner.initialize_conversation()

        assert runner.conversation_id == mock_conversation_id
        assert runner.conversation == mock_conversation
        mock_setup.assert_called_once_with(
            mock_conversation_id,
            include_security_analyzer=False,
            visualizer=None,
        )

    def test_is_running_property(self):
        """Test the is_running property."""
        runner = MinimalConversationRunner()

        # Initially not running
        assert runner.is_running is False

        # Set running state
        runner._running = True
        assert runner.is_running is True

        # Set not running state
        runner._running = False
        assert runner.is_running is False

    def test_current_conversation_id_property(self):
        """Test the current_conversation_id property."""
        runner = MinimalConversationRunner()

        # Initially None
        assert runner.current_conversation_id is None

        # Set conversation ID
        import uuid

        test_id = uuid.uuid4()
        runner.conversation_id = test_id
        assert runner.current_conversation_id == str(test_id)

    def test_pause_when_running(self):
        """Test pause method when conversation is running."""
        runner = MinimalConversationRunner()

        # Mock conversation
        mock_conversation = mock.MagicMock()
        runner.conversation = mock_conversation
        runner._running = True

        # Call pause
        runner.pause()

        # Verify pause was called on conversation
        mock_conversation.pause.assert_called_once()

    def test_pause_when_not_running(self):
        """Test pause method when conversation is not running."""
        runner = MinimalConversationRunner()

        # Mock conversation
        mock_conversation = mock.MagicMock()
        runner.conversation = mock_conversation
        runner._running = False

        # Call pause
        runner.pause()

        # Verify pause was NOT called on conversation
        mock_conversation.pause.assert_not_called()

    def test_pause_when_no_conversation(self):
        """Test pause method when no conversation exists."""
        runner = MinimalConversationRunner()

        # No conversation
        runner.conversation = None
        runner._running = True

        # Call pause - should not raise an exception
        runner.pause()

        # No assertions needed - just verify it doesn't crash

    def test_queue_message_assertion(self):
        """Test queue_message raises assertion when no conversation."""
        runner = MinimalConversationRunner()

        with pytest.raises(AssertionError, match="Conversation should be running"):
            runner.queue_message("test message")

    def test_queue_message_assertion_empty_input(self):
        """Test queue_message raises assertion with empty input."""
        runner = MinimalConversationRunner()

        # Mock conversation
        mock_conversation = mock.MagicMock()
        runner.conversation = mock_conversation

        with pytest.raises(AssertionError):
            runner.queue_message("")

    @mock.patch("openhands_cli.refactor.conversation_runner.setup_conversation")
    @mock.patch("uuid.uuid4")
    async def test_process_message_async_initializes_conversation(
        self, mock_uuid, mock_setup
    ):
        """Test that process_message_async initializes conversation if needed."""
        mock_conversation_id = mock.MagicMock()
        mock_uuid.return_value = mock_conversation_id
        mock_conversation = mock.MagicMock()
        mock_setup.return_value = mock_conversation

        runner = MinimalConversationRunner()

        # Mock the executor to avoid actual threading
        with mock.patch("asyncio.get_event_loop") as mock_loop:
            # Create a proper async mock
            async def mock_executor_func(executor, func, *args):
                return func(*args)

            mock_loop.return_value.run_in_executor = mock_executor_func

            await runner.process_message_async("test message")

            # Verify conversation was initialized
            assert runner.conversation_id == mock_conversation_id
            assert runner.conversation == mock_conversation

    def test_run_conversation_sync_sets_running_state(self):
        """Test that _run_conversation_sync properly manages running state."""
        runner = MinimalConversationRunner()

        # Mock conversation
        mock_conversation = mock.MagicMock()
        runner.conversation = mock_conversation

        # Mock message
        from openhands.sdk import Message, TextContent

        message = Message(role="user", content=[TextContent(text="test")])

        # Call the sync method
        runner._run_conversation_sync(message)

        # Verify conversation methods were called
        mock_conversation.send_message.assert_called_once_with(message)
        mock_conversation.run.assert_called_once()

        # Verify running state is reset
        assert runner._running is False

    def test_run_conversation_sync_handles_exception(self):
        """Test that _run_conversation_sync resets running state even on exception."""
        runner = MinimalConversationRunner()

        # Mock conversation that raises exception
        mock_conversation = mock.MagicMock()
        mock_conversation.run.side_effect = Exception("Test exception")
        runner.conversation = mock_conversation

        # Mock message
        from openhands.sdk import Message, TextContent

        message = Message(role="user", content=[TextContent(text="test")])

        # Call the sync method - should not raise because exception is caught
        try:
            runner._run_conversation_sync(message)
        except Exception:
            pass  # Exception is expected but should be handled

        # Verify running state is reset even after exception
        assert runner._running is False

    def test_run_conversation_sync_no_conversation(self):
        """Test that _run_conversation_sync handles no conversation gracefully."""
        runner = MinimalConversationRunner()

        # No conversation
        runner.conversation = None

        # Mock message
        from openhands.sdk import Message, TextContent

        message = Message(role="user", content=[TextContent(text="test")])

        # Call the sync method - should not raise
        runner._run_conversation_sync(message)

        # Verify running state is reset
        assert runner._running is False
