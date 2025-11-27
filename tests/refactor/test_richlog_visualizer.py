"""Tests for TextualVisualizer integration."""

import unittest
from unittest import mock

from openhands_cli.refactor.richlog_visualizer import TextualVisualizer


class TestTextualVisualizer(unittest.TestCase):
    """Test the TextualVisualizer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_container = mock.MagicMock()
        self.mock_app = mock.MagicMock()
        self.visualizer = TextualVisualizer(
            container=self.mock_container, app=self.mock_app, skip_user_messages=False
        )

    def test_visualizer_initialization(self):
        """Test that the visualizer initializes correctly."""
        self.assertIsNotNone(self.visualizer)
        self.assertEqual(self.visualizer._container, self.mock_container)
        self.assertEqual(self.visualizer._app, self.mock_app)
        self.assertFalse(self.visualizer._skip_user_messages)

    def test_visualizer_with_skip_user_messages(self):
        """Test that skip_user_messages option is set correctly."""
        visualizer = TextualVisualizer(
            container=self.mock_container, app=self.mock_app, skip_user_messages=True
        )
        self.assertTrue(visualizer._skip_user_messages)

    def test_on_event_with_unknown_event(self):
        """Test that on_event handles unknown events gracefully."""
        # Create a mock event that won't be in the visualization config
        mock_event = mock.MagicMock()
        mock_event.__class__.__name__ = "UnknownEvent"
        mock_event.visualize.plain = "Test content"
        mock_event.source = "test"

        # Should not raise an exception
        try:
            self.visualizer.on_event(mock_event)
        except Exception as e:
            self.fail(f"on_event raised an exception: {e}")

        # Container mount should be called for unknown events (they get a fallback
        # widget)
        self.mock_container.mount.assert_called_once()

    def test_container_is_stored(self):
        """Test that the container is properly stored."""
        self.assertEqual(self.visualizer._container, self.mock_container)

    def test_visualizer_inheritance(self):
        """Test that TextualVisualizer inherits from ConversationVisualizerBase."""
        from openhands.sdk.conversation.visualizer.base import (
            ConversationVisualizerBase,
        )

        self.assertIsInstance(self.visualizer, ConversationVisualizerBase)


if __name__ == "__main__":
    unittest.main()
