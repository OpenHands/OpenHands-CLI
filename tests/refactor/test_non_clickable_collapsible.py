"""Tests for NonClickableCollapsible component."""

import unittest
from unittest.mock import MagicMock, patch

from openhands_cli.refactor.widgets.non_clickable_collapsible import (
    NonClickableCollapsible,
)


class TestNonClickableCollapsible(unittest.TestCase):
    """Test cases for NonClickableCollapsible component."""

    def test_constructor_accepts_string_content(self):
        """Test that constructor accepts string content parameter."""
        test_content = "This is test content"
        component = NonClickableCollapsible(
            content=test_content,
            title="Test Title",
            collapsed=True,
            border_color="blue",  # Use a valid color instead of CSS variable
        )

        # Verify the content string is stored
        self.assertEqual(component._content_string, test_content)

        # Verify the content widget is created
        self.assertIsNotNone(component._content_widget)
        # Static widget stores content in its content attribute
        self.assertEqual(component._content_widget.content, test_content)

    def test_content_string_stores_original_string(self):
        """Test that _content_string stores the original string parameter."""
        test_content = "This is test content with special characters: !@#$%^&*()"
        component = NonClickableCollapsible(
            content=test_content,
            title="Test Title",
            collapsed=True,
            border_color="green",
        )

        # Test that the attribute stores the exact original string
        self.assertEqual(component._content_string, test_content)

    def test_copy_functionality_with_multiline_content(self):
        """Test copy functionality with multiline content."""
        test_content = """Line 1
Line 2
Line 3 with special chars: !@#$%^&*()"""

        component = NonClickableCollapsible(
            content=test_content, title="Test Title", collapsed=True, border_color="red"
        )

        # Test that the attribute stores the exact original multiline string
        self.assertEqual(component._content_string, test_content)

    def test_copy_to_clipboard_action(self):
        """Test that copy action calls app.copy_to_clipboard with correct content."""
        test_content = "Content to be copied"
        component = NonClickableCollapsible(
            content=test_content,
            title="Test Title",
            collapsed=True,
            border_color="yellow",
        )

        # Mock the app and its methods
        mock_app = MagicMock()

        # Mock the app property since it's read-only
        with patch.object(type(component), "app", new_callable=lambda: mock_app):
            # Create a mock event to trigger the copy
            from openhands_cli.refactor.widgets.non_clickable_collapsible import (
                NonClickableCollapsibleTitle,
            )

            mock_event = MagicMock(spec=NonClickableCollapsibleTitle.CopyRequested)

            # Simulate the copy action by calling the event handler directly
            component._on_non_clickable_collapsible_title_copy_requested(mock_event)

            # Verify app.copy_to_clipboard was called with the correct content
            mock_app.copy_to_clipboard.assert_called_once_with(test_content)

            # Verify a notification was posted
            mock_app.notify.assert_called_once()

    def test_compose_yields_content_widget(self):
        """Test that compose method yields the internal content widget."""
        test_content = "Test content for compose"
        component = NonClickableCollapsible(
            content=test_content,
            title="Test Title",
            collapsed=True,
            border_color="purple",
        )

        # We can't test compose() directly without an app context
        # Instead, verify that the content widget exists and has the right content
        self.assertIsNotNone(component._content_widget)
        self.assertEqual(component._content_widget.content, test_content)

    def test_different_content_types_converted_to_string(self):
        """Test that different content types are properly converted to strings."""
        # Test with integer
        component_int = NonClickableCollapsible(
            content=12345, title="Integer Test", collapsed=True, border_color="orange"
        )
        self.assertEqual(component_int._content_string, "12345")

        # Test with list (should be converted to string representation)
        test_list = [1, 2, 3]
        component_list = NonClickableCollapsible(
            content=test_list, title="List Test", collapsed=True, border_color="cyan"
        )
        self.assertEqual(component_list._content_string, str(test_list))


if __name__ == "__main__":
    unittest.main()
