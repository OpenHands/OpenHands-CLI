"""Tests for ConversationVisualizer and Chinese character markup handling."""

from typing import TYPE_CHECKING

import pytest
from rich.errors import MarkupError
from rich.text import Text
from textual.app import App
from textual.containers import VerticalScroll
from textual.widgets import Static

from openhands.sdk import Action, MessageEvent, TextContent
from openhands.sdk.event import ActionEvent
from openhands.sdk.event.conversation_error import ConversationErrorEvent
from openhands.sdk.llm import MessageToolCall
from openhands_cli.refactor.widgets.richlog_visualizer import ConversationVisualizer


if TYPE_CHECKING:
    pass


class RichLogMockAction(Action):
    """Mock action for testing rich log visualizer."""

    command: str = "test command"


def create_tool_call(
    call_id: str, function_name: str, arguments: str = "{}"
) -> MessageToolCall:
    """Helper to create a MessageToolCall."""
    return MessageToolCall(
        id=call_id,
        name=function_name,
        arguments=arguments,
        origin="completion",
    )


class TestChineseCharacterMarkupHandling:
    """Tests for handling Chinese characters with special markup symbols."""

    def test_escape_rich_markup_escapes_brackets(self):
        """Test that _escape_rich_markup properly escapes square brackets."""
        # Create a mock app and container for the visualizer
        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

        # Test escaping with various bracket patterns
        test_cases = [
            ("[test]", r"\[test\]"),
            ("处于历史40%分位]", r"处于历史40%分位\]"),
            ("[cyan]colored[/cyan]", r"\[cyan\]colored\[/cyan\]"),
            (
                "+0.3%,月变化+0.8%,处于历史40%分位]",
                r"+0.3%,月变化+0.8%,处于历史40%分位\]",
            ),
        ]

        for input_text, expected_output in test_cases:
            result = visualizer._escape_rich_markup(input_text)
            assert result == expected_output, (
                f"Failed to escape '{input_text}': expected '{expected_output}', "
                f"got '{result}'"
            )

    def test_safe_content_string_escapes_problematic_content(self):
        """Test that _escape_rich_markup escapes MarkupError content."""
        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

        # Example content that caused the original error
        problematic_content = "+0.3%,月变化+0.8%,处于历史40%分位]"
        safe_content = visualizer._escape_rich_markup(str(problematic_content))

        # Verify brackets are escaped
        assert r"\]" in safe_content
        # Verify Chinese characters are preserved
        assert "月变化" in safe_content
        assert "处于历史" in safe_content

    def test_unescaped_content_with_close_tag_causes_markup_error(self):
        """Verify that certain bracket patterns can cause MarkupError.

        This test demonstrates the problem that can occur with unescaped brackets.
        """

        # Content with close tag but no open tag - this WILL cause an error
        problematic_content = "[/close_without_open]"

        # Without escaping, this raises a MarkupError when parsed as markup
        with pytest.raises(MarkupError) as exc_info:
            Text.from_markup(problematic_content)

        assert "closing tag" in str(exc_info.value).lower()

    def test_escaped_chinese_content_renders_successfully(self):
        """Verify escaped Chinese chars and brackets render correctly.

        This test demonstrates that the fix resolves the issue.
        """
        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

        # Content with Chinese characters and special markup characters
        problematic_content = "+0.3%,月变化+0.8%,处于历史40%分位]"

        # Use the _escape_rich_markup method (the fix)
        safe_content = visualizer._escape_rich_markup(str(problematic_content))

        # This should NOT raise an error
        widget = Static(safe_content, markup=True)
        # Force rendering to verify it works
        rendered = widget.render()

        # Verify the content is present in the rendered output
        assert rendered is not None

    def test_visualizer_handles_chinese_action_event(self):
        """Test that visualizer can handle ActionEvent with Chinese content."""
        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

        # Create an action with Chinese content
        action = RichLogMockAction(command="分析数据: [结果+0.3%]")
        tool_call = create_tool_call("call_1", "test")

        action_event = ActionEvent(
            thought=[TextContent(text="Testing Chinese characters with brackets")],
            action=action,
            tool_name="test",
            tool_call_id="call_1",
            tool_call=tool_call,
            llm_response_id="response_1",
        )

        # This should not raise an error
        collapsible = visualizer._create_event_collapsible(action_event)
        assert collapsible is not None

    def test_visualizer_handles_chinese_message_event(self):
        """Test that visualizer can handle MessageEvent with Chinese content."""
        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

        # Create a message with problematic Chinese content
        from openhands.sdk import Message

        message = Message(
            role="assistant",
            content=[
                TextContent(
                    text="根据分析，增长率为+0.3%,月变化+0.8%,处于历史40%分位]的数据。"
                )
            ],
        )

        message_event = MessageEvent(llm_message=message, source="agent")

        # This should not raise an error
        collapsible = visualizer._create_event_collapsible(message_event)
        assert collapsible is not None

    @pytest.mark.parametrize(
        "test_content",
        [
            # Chinese with brackets
            "测试[内容]",
            # Chinese with percentage and brackets
            "+0.3%,月变化+0.8%,处于历史40%分位]",
            # Multiple bracket pairs
            "[开始]处理数据[结束]",
            # Complex markup-like patterns
            "[cyan]彩色文字[/cyan]",
            # Mixed English and Chinese
            "Processing [处理中] 100%",
        ],
    )
    def test_various_chinese_patterns_are_escaped(self, test_content):
        """Test that various patterns of Chinese text with special chars are handled."""
        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

        # Use the _escape_rich_markup method
        safe_content = visualizer._escape_rich_markup(str(test_content))

        # Verify brackets are escaped
        assert "[" not in safe_content or r"\[" in safe_content
        assert "]" not in safe_content or r"\]" in safe_content

        # Should be able to create a Static widget without error
        widget = Static(safe_content, markup=True)
        rendered = widget.render()
        assert rendered is not None


class TestVisualizerWithoutEscaping:
    """Tests that demonstrate what happens WITHOUT the escaping fix.

    These tests show that the fix is necessary by demonstrating specific
    bracket patterns that cause MarkupError.
    """

    def test_close_tag_without_open_causes_error(self):
        """Demonstrate that close tag without open causes MarkupError."""

        # Close tag without matching open tag
        problematic_text = "[/bold]"

        # This causes a markup error
        with pytest.raises(MarkupError) as exc_info:
            Text.from_markup(problematic_text)

        assert "closing tag" in str(exc_info.value).lower()

    def test_escaping_prevents_markup_interpretation(self):
        """Demonstrate escaping prevents bracket markup interpretation."""

        # Content that looks like a close tag
        content_with_brackets = "Result [/end]"

        # Without escaping, this causes an error
        with pytest.raises(MarkupError):
            Text.from_markup(content_with_brackets)

        # With escaping, it works fine
        escaped_content = content_with_brackets.replace("[", r"\[").replace("]", r"\]")
        text = Text.from_markup(escaped_content)
        # The escaped markup preserves the bracket characters in the rendered output
        assert "[/end" in text.plain  # Brackets are preserved (with escape char)


class TestVisualizerIntegration:
    """Integration tests for the visualizer with Chinese content."""

    def test_end_to_end_chinese_content_visualization(self):
        """End-to-end test: create event with Chinese content and visualize it."""
        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

        # Create realistic event with problematic content
        action = RichLogMockAction(
            command="分析结果: 增长率+0.3%,月变化+0.8%,处于历史40%分位]"
        )
        tool_call = create_tool_call("call_test", "analyze")

        event = ActionEvent(
            thought=[TextContent(text="执行分析")],
            action=action,
            tool_name="analyze",
            tool_call_id="call_test",
            tool_call=tool_call,
            llm_response_id="resp_test",
        )

        # This entire flow should work without errors
        collapsible = visualizer._create_event_collapsible(event)
        assert collapsible is not None
        assert collapsible.title is not None

        # The title should contain escaped content
        title_str = str(collapsible.title)
        # If brackets were in the original, they should be escaped in the output
        if "[" in action.command or "]" in action.command:
            # The title extraction should have escaped them
            assert r"\[" in title_str or r"\]" in title_str


class TestConversationErrorEventHandling:
    """Tests for ConversationErrorEvent handling in the visualizer."""

    def test_conversation_error_event_creates_collapsible_with_error_styling(self):
        """Test that ConversationErrorEvent is properly handled with error styling."""
        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

        # Create a ConversationErrorEvent with test content
        error_event = ConversationErrorEvent(
            source="agent", code="test_error", detail="Test conversation error message"
        )

        # Create the collapsible widget for the error event
        collapsible = visualizer._create_event_collapsible(error_event)

        # Verify the collapsible was created successfully
        assert collapsible is not None

        # Verify it has the correct title
        assert "Conversation Error" in str(collapsible.title)

        # Verify it starts expanded (collapsed=False)
        assert not collapsible.collapsed

        # Verify it has error border color (should be the error theme color)
        from openhands_cli.refactor.widgets.richlog_visualizer import (
            _get_event_border_color,
        )
        from openhands_cli.theme import OPENHANDS_THEME

        expected_color = OPENHANDS_THEME.error or "#ff6b6b"
        actual_color = _get_event_border_color(error_event)
        assert actual_color == expected_color
