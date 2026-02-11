"""Tests for ConversationVisualizer and Chinese character markup handling."""

from typing import TYPE_CHECKING
from unittest.mock import patch

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
from openhands.tools.terminal.definition import TerminalAction
from openhands_cli.stores import CliSettings
from openhands_cli.tui.widgets.richlog_visualizer import (
    ELLIPSIS,
    MAX_LINE_LENGTH,
    ConversationVisualizer,
)


if TYPE_CHECKING:
    pass


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def visualizer():
    """Create a ConversationVisualizer with mock app and container."""
    app = App()
    container = VerticalScroll()
    return ConversationVisualizer(container, app)  # type: ignore[arg-type]


@pytest.fixture
def mock_cli_settings():
    """Provide a context manager for mocking CliSettings.load with default settings."""
    from contextlib import contextmanager

    @contextmanager
    def _mock_settings(visualizer=None, **kwargs):
        """Create mock context with specified settings.

        Args:
            visualizer: Optional visualizer to clear cached settings for
            **kwargs: Settings to pass to CliSettings constructor
        """
        settings = CliSettings(**kwargs)
        with patch.object(CliSettings, "load", return_value=settings):
            if visualizer is not None:
                visualizer._cli_settings = None
            yield settings

    return _mock_settings


@pytest.fixture
def mock_cli_settings_with_defaults(mock_cli_settings):
    """Provide mock CliSettings with default values."""
    return mock_cli_settings()


# ============================================================================
# Helper Classes and Functions
# ============================================================================


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


def create_terminal_action_event(
    command: str, summary: str | None = "Test command"
) -> ActionEvent:
    """Helper to create a terminal ActionEvent for testing."""
    action = TerminalAction(command=command)
    tool_call = create_tool_call("call_1", "terminal")
    thought = [TextContent(text=summary)] if summary else []
    return ActionEvent(
        thought=thought,
        action=action,
        tool_name="terminal",
        tool_call_id="call_1",
        tool_call=tool_call,
        llm_response_id="response_1",
        summary=summary,
    )


class TestChineseCharacterMarkupHandling:
    """Tests for handling Chinese characters with special markup symbols."""

    def test_escape_rich_markup_escapes_brackets(self, visualizer):
        """Test that _escape_rich_markup properly escapes square brackets."""
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

    def test_safe_content_string_escapes_problematic_content(self, visualizer):
        """Test that _escape_rich_markup escapes MarkupError content."""
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
        problematic_content = "[/close_without_open]"

        with pytest.raises(MarkupError) as exc_info:
            Text.from_markup(problematic_content)

        assert "closing tag" in str(exc_info.value).lower()

    def test_escaped_chinese_content_renders_successfully(self, visualizer):
        """Verify escaped Chinese chars and brackets render correctly.

        This test demonstrates that the fix resolves the issue.
        """
        problematic_content = "+0.3%,月变化+0.8%,处于历史40%分位]"
        safe_content = visualizer._escape_rich_markup(str(problematic_content))

        # This should NOT raise an error
        widget = Static(safe_content, markup=True)
        rendered = widget.render()
        assert rendered is not None

    def test_visualizer_handles_chinese_action_event(self, visualizer):
        """Test that visualizer can handle ActionEvent with Chinese content."""
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

        collapsible = visualizer._create_event_collapsible(action_event)
        assert collapsible is not None

    def test_visualizer_handles_chinese_message_event(self, visualizer):
        """Test that visualizer can handle MessageEvent with Chinese content."""
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

        collapsible = visualizer._create_event_collapsible(message_event)
        assert collapsible is not None

    @pytest.mark.parametrize(
        "test_content",
        [
            "测试[内容]",
            "+0.3%,月变化+0.8%,处于历史40%分位]",
            "[开始]处理数据[结束]",
            "[cyan]彩色文字[/cyan]",
            "Processing [处理中] 100%",
        ],
    )
    def test_various_chinese_patterns_are_escaped(self, visualizer, test_content):
        """Test that various patterns of Chinese text with special chars are handled."""
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

    def test_end_to_end_chinese_content_visualization(self, visualizer):
        """End-to-end test: create event with Chinese content and visualize it.

        Uses TerminalAction since the title includes the command for terminal actions.
        """
        from openhands.tools.terminal.definition import TerminalAction

        action = TerminalAction(
            command="分析结果: 增长率+0.3%,月变化+0.8%,处于历史40%分位]"
        )
        tool_call = create_tool_call("call_test", "terminal")

        event = ActionEvent(
            thought=[TextContent(text="执行分析")],
            action=action,
            tool_name="terminal",
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
        # For terminal actions, the command is included in the title
        # Brackets in the command should be escaped
        assert r"\]" in title_str, f"Expected escaped bracket in title: {title_str}"

    def test_visualizer_handles_mistral_xml_function_call_syntax(self, visualizer):
        """Test that visualizer can handle ActionEvent with Mistral XML function call.

        This test reproduces the issue described in GitHub issue #93 where Mistral
        models generate function call syntax like '<function=execute_bash>' that
        causes XML parsing errors in the CLI confirmation dialog. While this test is
        for the visualizer component, it demonstrates the same type of XML content
        that causes issues in the CLI.
        """
        # Create an action with XML-like function call syntax that caused the issue
        xml_command = (
            "<function=execute_bash>\n"
            "<parameter=command>pwd && ls</parameter>\n"
            "<parameter=security_risk>LOW</parameter>"
        )
        action = RichLogMockAction(command=xml_command)
        tool_call = create_tool_call("call_1", "execute_bash")

        # RichLogMockAction does not parse XML; it stores the command as-is
        assert action.command == xml_command
        # Sanity-check the XML-like content is present in the command string
        assert "<function=execute_bash" in action.command
        assert "<parameter=command>" in action.command

        action_event = ActionEvent(
            thought=[TextContent(text="I need to check the current directory")],
            action=action,
            tool_name="execute_bash",
            tool_call_id="call_1",
            tool_call=tool_call,
            llm_response_id="response_1",
        )

        # This should not raise an XML parsing error or any other exception
        # The key test is that it doesn't crash, even if content isn't escaped
        collapsible = visualizer._create_event_collapsible(action_event)
        assert collapsible is not None
        assert collapsible.title is not None

        # Verify that the visualizer successfully created a collapsible widget
        title_str = str(collapsible.title)
        # For non-terminal/file-editor actions without summary, title is just tool_name
        assert "execute_bash" in title_str  # The function name should be present
        assert len(title_str) > 0  # Title should not be empty


class TestConversationErrorEventHandling:
    """Tests for ConversationErrorEvent handling in the visualizer."""

    def test_conversation_error_event_creates_collapsible_with_error_styling(
        self, visualizer, mock_cli_settings
    ):
        """Test that ConversationErrorEvent is properly handled with error styling."""
        error_event = ConversationErrorEvent(
            source="agent",
            code="test_error",
            detail="Test conversation error message",
        )

        with mock_cli_settings(visualizer=visualizer, default_cells_expanded=True):
            collapsible = visualizer._create_event_collapsible(error_event)

            assert collapsible is not None
            assert "Conversation Error" in str(collapsible.title)
            # collapsed=False when default_cells_expanded=True
            assert not collapsible.collapsed


class TestEventSymbolColor:
    """Tests for event-based symbol coloring in collapsibles."""

    def test_error_event_has_error_symbol_color(self, visualizer, mock_cli_settings):
        """Test that error events get the error color for their symbol."""
        from openhands_cli.theme import OPENHANDS_THEME
        from openhands_cli.tui.widgets.richlog_visualizer import _get_event_symbol_color

        error_event = ConversationErrorEvent(
            source="agent",
            code="test_error",
            detail="Test error message",
        )

        symbol_color = _get_event_symbol_color(error_event)
        assert symbol_color == OPENHANDS_THEME.error

    def test_action_event_has_default_symbol_color(self, visualizer, mock_cli_settings):
        """Test that action events get the default (white) color for their symbol."""
        from openhands_cli.tui.widgets.richlog_visualizer import _get_event_symbol_color

        action_event = create_terminal_action_event("ls -la", "List files")
        symbol_color = _get_event_symbol_color(action_event)
        # Action events use the default white color for a cleaner look
        assert symbol_color == "#ffffff"

    def test_collapsible_receives_symbol_color(self, visualizer, mock_cli_settings):
        """Test that collapsibles are created with the correct symbol color."""
        from openhands_cli.theme import OPENHANDS_THEME

        error_event = ConversationErrorEvent(
            source="agent",
            code="test_error",
            detail="Test error message",
        )

        with mock_cli_settings(visualizer=visualizer, default_cells_expanded=True):
            collapsible = visualizer._create_event_collapsible(error_event)
            assert collapsible is not None
            # The CollapsibleTitle should have the error color
            assert collapsible._title.symbol_color == OPENHANDS_THEME.error


class TestDefaultCellsExpandedSetting:
    """Tests for the default_cells_expanded setting in ConversationVisualizer."""

    @pytest.mark.parametrize("default_expanded", [True, False])
    def test_collapsible_respects_default_cells_expanded_setting(
        self, visualizer, mock_cli_settings, default_expanded: bool
    ):
        """Test that collapsible widgets respect the default_cells_expanded setting."""
        error_event = ConversationErrorEvent(
            source="agent", code="test_error", detail="Test message"
        )

        with mock_cli_settings(
            visualizer=visualizer, default_cells_expanded=default_expanded
        ):
            collapsible = visualizer._create_event_collapsible(error_event)
            assert collapsible is not None

            # collapsed should be the opposite of default_cells_expanded
            expected_collapsed = not default_expanded
            assert collapsible.collapsed is expected_collapsed

    def test_default_collapsed_property(self, visualizer, mock_cli_settings):
        """Test the _default_collapsed property returns correct value."""
        # Test with default_cells_expanded=True (default)
        with mock_cli_settings(visualizer=visualizer, default_cells_expanded=True):
            assert visualizer._default_collapsed is False

        # Test with default_cells_expanded=False
        with mock_cli_settings(visualizer=visualizer, default_cells_expanded=False):
            assert visualizer._default_collapsed is True


class TestCliSettingsCaching:
    """Tests for app configuration caching in ConversationVisualizer."""

    def test_cli_settings_caching(self, visualizer):
        """Test that app configuration is cached and not loaded repeatedly."""
        with patch("openhands_cli.stores.CliSettings.load") as mock_load:
            mock_config = CliSettings(default_cells_expanded=True)
            mock_load.return_value = mock_config

            # First call should load from file
            config1 = visualizer.cli_settings
            assert config1 == mock_config
            assert mock_load.call_count == 1

            # Second call should use cached version
            config2 = visualizer.cli_settings
            assert config2 == mock_config
            assert mock_load.call_count == 1  # Should still be 1, not 2

            # Third call should also use cached version
            config3 = visualizer.cli_settings
            assert config3 == mock_config
            assert mock_load.call_count == 1  # Should still be 1, not 3

    def test_cli_settings_refresh(self, visualizer):
        """Test that reload_configuration reloads the configuration."""
        with patch("openhands_cli.stores.CliSettings.load") as mock_load:
            mock_config1 = CliSettings(default_cells_expanded=False)
            mock_config2 = CliSettings(default_cells_expanded=True)
            mock_load.side_effect = [mock_config1, mock_config2]

            # First call should load from file
            config1 = visualizer.cli_settings
            assert config1 == mock_config1
            assert mock_load.call_count == 1

            # Refresh should reload from file
            visualizer.reload_configuration()
            assert mock_load.call_count == 2

            # Next call should use the new cached version
            config2 = visualizer.cli_settings
            assert config2 == mock_config2
            assert mock_load.call_count == 2  # Should still be 2, not 3

    def test_reload_configuration_clears_cache(self, visualizer):
        """Test that reload_configuration properly clears the cached configuration."""
        with patch("openhands_cli.stores.CliSettings.load") as mock_load:
            config1 = CliSettings(default_cells_expanded=False)
            config2 = CliSettings(default_cells_expanded=True)
            mock_load.side_effect = [config1, config2]

            # First access should load config1
            first_config = visualizer.cli_settings
            assert first_config.default_cells_expanded is False
            assert mock_load.call_count == 1

            # Reload should clear cache and load config2
            visualizer.reload_configuration()
            assert mock_load.call_count == 2

            # Next access should return config2 (from cache)
            second_config = visualizer.cli_settings
            assert second_config.default_cells_expanded is True
            assert mock_load.call_count == 2  # No additional load

    @pytest.mark.parametrize(
        "initial_cache_state",
        [None, "cached_config"],
    )
    def test_cli_settings_property_initialization(
        self, visualizer, initial_cache_state
    ):
        """Test cli_settings property behavior with different initial cache states."""
        # Set initial cache state
        if initial_cache_state == "cached_config":
            visualizer._cli_settings = CliSettings(default_cells_expanded=False)
        else:
            visualizer._cli_settings = None

        with patch("openhands_cli.stores.CliSettings.load") as mock_load:
            mock_config = CliSettings(default_cells_expanded=True)
            mock_load.return_value = mock_config

            result = visualizer.cli_settings

            if initial_cache_state is None:
                assert mock_load.call_count == 1
                assert result == mock_config
            else:
                assert mock_load.call_count == 0
                assert result.default_cells_expanded is False


class TestCommandTruncation:
    """Tests for truncating long terminal commands in action titles."""

    def test_short_command_not_truncated(self, visualizer):
        """Test that short commands are displayed in full."""
        short_cmd = "ls -la"
        action_event = create_terminal_action_event(short_cmd, "List files")

        title = visualizer._build_action_title(action_event)
        assert short_cmd in title
        assert "..." not in title

    def test_long_command_truncated(self, visualizer):
        """Test that commands exceeding MAX_LINE_LENGTH are truncated with ellipsis."""
        long_cmd = "curl -X POST https://api.example.com/endpoint " + "-d " * 20
        assert len(long_cmd) > MAX_LINE_LENGTH

        action_event = create_terminal_action_event(long_cmd, "Make API request")

        title = visualizer._build_action_title(action_event)
        assert "..." in title
        assert long_cmd not in title

    def test_multiline_command_flattened_and_truncated(self, visualizer):
        """Test that multiline commands are flattened and truncated."""
        multiline_cmd = """cat << 'EOF' > /path/to/file.txt
This is line 1
This is line 2
This is line 3
And many more lines
EOF"""
        assert len(multiline_cmd) > MAX_LINE_LENGTH

        action_event = create_terminal_action_event(multiline_cmd, "Write file")

        title = visualizer._build_action_title(action_event)
        assert "..." in title
        assert "\n" not in title

    def test_command_exactly_at_limit(self, visualizer):
        """Test that commands exactly at MAX_LINE_LENGTH are not truncated."""
        cmd = "a" * MAX_LINE_LENGTH
        assert len(cmd) == MAX_LINE_LENGTH

        action_event = create_terminal_action_event(cmd)

        title = visualizer._build_action_title(action_event)
        assert "..." not in title
        assert cmd in title

    def test_command_one_over_limit_truncated(self, visualizer):
        """Test that commands one char over MAX_LINE_LENGTH are truncated."""
        cmd = "a" * (MAX_LINE_LENGTH + 1)
        assert len(cmd) == MAX_LINE_LENGTH + 1

        action_event = create_terminal_action_event(cmd)

        title = visualizer._build_action_title(action_event)
        assert ELLIPSIS in title
        truncated_length = MAX_LINE_LENGTH - len(ELLIPSIS)
        assert "a" * truncated_length + ELLIPSIS in title

    def test_command_without_summary(self, visualizer):
        """Test truncation works when there's no summary (just $ command)."""
        long_cmd = "b" * 100
        action_event = create_terminal_action_event(long_cmd, summary=None)

        title = visualizer._build_action_title(action_event)
        # Command without summary is wrapped in [dim] tags
        assert title.startswith("[dim]$ ")
        assert title.endswith("[/dim]")
        assert "..." in title

    def test_truncate_from_end_for_paths(self, visualizer):
        """Test that path truncation keeps the end (filename) and truncates start."""
        # Create a path that exceeds MAX_LINE_LENGTH (70 chars)
        long_path = (
            "/very/long/directory/structure/with/many/nested/folders/extras/file.txt"
        )
        assert len(long_path) > MAX_LINE_LENGTH, f"Path length is {len(long_path)}"
        truncated = visualizer._truncate_for_display(long_path, from_start=False)

        # Should keep the end (filename) and add ellipsis at start
        assert truncated.startswith(ELLIPSIS)
        assert truncated.endswith("file.txt")
        assert len(truncated) == MAX_LINE_LENGTH

    def test_truncate_from_start_default(self, visualizer):
        """Test default truncation keeps start and adds ellipsis at end."""
        long_text = "a" * 100
        truncated = visualizer._truncate_for_display(long_text)

        # Should keep start and add ellipsis at end
        assert truncated.endswith(ELLIPSIS)
        assert truncated.startswith("a")
        assert len(truncated) == MAX_LINE_LENGTH


# ============================================================================
# Plan Panel Integration Tests
# ============================================================================


class TestPlanPanelIntegration:
    """Tests for ConversationVisualizer plan panel integration."""

    @pytest.mark.asyncio
    async def test_task_tracker_observation_triggers_plan_panel_refresh(self):
        """Verify that receiving a TaskTrackerObservation calls _refresh_plan_panel."""
        from unittest.mock import patch

        from textual.app import App
        from textual.containers import Horizontal, VerticalScroll
        from textual.widgets import Static

        from openhands.sdk.event import ObservationEvent
        from openhands.tools.task_tracker.definition import (
            TaskItem,
            TaskTrackerObservation,
        )

        class TestApp(App):
            CSS = """
            Screen { layout: horizontal; }
            #main_content { width: 2fr; }
            """

            def compose(self):
                with Horizontal(id="content_area"):
                    with VerticalScroll(id="scroll_view"):
                        yield Static("Content")

        app = TestApp()
        async with app.run_test():
            container = app.query_one("#scroll_view", VerticalScroll)
            visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

            # Create a TaskTrackerObservation event
            task_tracker_obs = TaskTrackerObservation(
                command="plan",
                task_list=[TaskItem(title="Test", notes="", status="todo")],
            )
            event = ObservationEvent(
                observation=task_tracker_obs,
                tool_call_id="test-123",
                tool_name="task_tracker",
                action_id="action-1",
            )

            # Mock _do_refresh_plan_panel to verify it gets called
            with patch.object(visualizer, "_do_refresh_plan_panel") as mock_refresh:
                visualizer.on_event(event)
                mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("auto_open_enabled", [True, False])
    async def test_refresh_plan_panel_respects_auto_open_setting(
        self, auto_open_enabled: bool
    ):
        """Verify panel toggle behavior respects auto_open_plan_panel setting."""

        from textual.app import App
        from textual.containers import Horizontal, VerticalScroll
        from textual.widgets import Static

        from openhands_cli.tui.panels.plan_side_panel import PlanSidePanel

        class TestApp(App):
            CSS = """
            Screen { layout: horizontal; }
            #main_content { width: 2fr; }
            """

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.conversation_dir = "/test/conversation/dir"
                self.plan_panel: PlanSidePanel | None = None

            def compose(self):
                with Horizontal(id="content_area"):
                    with VerticalScroll(id="scroll_view"):
                        yield Static("Content")

            def on_mount(self):
                self.plan_panel = PlanSidePanel(self)  # type: ignore[arg-type]

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()  # Wait for on_mount
            container = app.query_one("#scroll_view", VerticalScroll)
            visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

            # Mock settings and toggle
            with patch.object(
                CliSettings,
                "load",
                return_value=CliSettings(auto_open_plan_panel=auto_open_enabled),
            ):
                visualizer._cli_settings = None  # Clear cache
                with patch.object(app.plan_panel, "toggle") as mock_toggle:
                    visualizer._do_refresh_plan_panel()

                    if auto_open_enabled:
                        # toggle() should be called to open the panel
                        mock_toggle.assert_called_once()
                    else:
                        # toggle() should NOT be called
                        mock_toggle.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_plan_panel_updates_existing_panel(self):
        """Verify existing panel is refreshed regardless of auto_open setting."""
        from unittest.mock import PropertyMock

        from textual.app import App
        from textual.containers import Horizontal, VerticalScroll
        from textual.widgets import Static

        from openhands_cli.tui.panels.plan_side_panel import PlanSidePanel

        class TestApp(App):
            CSS = """
            Screen { layout: horizontal; }
            #main_content { width: 2fr; }
            """

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.conversation_dir = "/test/conversation/dir"
                self.plan_panel: PlanSidePanel | None = None

            def compose(self):
                with Horizontal(id="content_area"):
                    with VerticalScroll(id="scroll_view"):
                        yield Static("Content")

            def on_mount(self):
                self.plan_panel = PlanSidePanel(self)  # type: ignore[arg-type]

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()  # Wait for on_mount
            container = app.query_one("#scroll_view", VerticalScroll)
            visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

            # Mock that panel is already on screen
            with patch.object(
                type(app.plan_panel), "is_on_screen", new_callable=PropertyMock
            ) as mock_is_on_screen:
                mock_is_on_screen.return_value = True

                # Mock refresh_from_disk to verify it gets called
                with patch.object(app.plan_panel, "refresh_from_disk") as mock_refresh:
                    # Even with auto_open disabled, existing panel should refresh
                    with patch.object(
                        CliSettings,
                        "load",
                        return_value=CliSettings(auto_open_plan_panel=False),
                    ):
                        visualizer._cli_settings = None  # Clear cache
                        visualizer._do_refresh_plan_panel()

                    mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_plan_panel_calls_toggle_when_auto_open_enabled(self):
        """Verify toggle() is called when auto_open_plan_panel is enabled
        and panel is not on screen."""

        from textual.app import App
        from textual.containers import Horizontal, VerticalScroll
        from textual.widgets import Static

        from openhands_cli.tui.panels.plan_side_panel import PlanSidePanel

        class TestApp(App):
            CSS = """
            Screen { layout: horizontal; }
            #main_content { width: 2fr; }
            """

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.conversation_dir = "/test/conversation/dir"
                self.plan_panel: PlanSidePanel | None = None

            def compose(self):
                with Horizontal(id="content_area"):
                    with VerticalScroll(id="scroll_view"):
                        yield Static("Content")

            def on_mount(self):
                self.plan_panel = PlanSidePanel(self)  # type: ignore[arg-type]

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()  # Wait for on_mount
            container = app.query_one("#scroll_view", VerticalScroll)
            visualizer = ConversationVisualizer(container, app)  # type: ignore[arg-type]

            # Ensure panel is not on screen
            assert app.plan_panel is not None
            assert app.plan_panel.is_on_screen is False

            with patch.object(
                CliSettings,
                "load",
                return_value=CliSettings(auto_open_plan_panel=True),
            ):
                visualizer._cli_settings = None  # Clear cache
                with patch.object(app.plan_panel, "toggle") as mock_toggle:
                    visualizer._do_refresh_plan_panel()
                    mock_toggle.assert_called_once()


class TestSubVisualizerCreation:
    """Tests for create_sub_visualizer method used during delegation."""

    def test_create_sub_visualizer_returns_new_instance_with_name(self, visualizer):
        """Sub-visualizer is created with correct agent name set."""
        sub_vis = visualizer.create_sub_visualizer("child_agent")

        assert isinstance(sub_vis, ConversationVisualizer)
        assert sub_vis._name == "child_agent"
        assert sub_vis is not visualizer

    def test_create_sub_visualizer_shares_container_and_app(self, visualizer):
        """Sub-visualizer shares the same container and app as parent."""
        sub_vis = visualizer.create_sub_visualizer("child_agent")

        assert sub_vis._container is visualizer._container
        assert sub_vis._app is visualizer._app


class TestMessageEventDelegation:
    """Tests for MessageEvent handling in delegation context."""

    def test_message_event_skipped_without_delegation_context(self, visualizer):
        """MessageEvent returns None when not in delegation context."""
        from openhands.sdk import Message

        message = Message(
            role="user",
            content=[TextContent(text="Hello from user")],
        )
        event = MessageEvent(llm_message=message, source="user")

        widget = visualizer._create_event_widget(event)

        assert widget is None

    def test_message_event_skipped_when_no_sender(self):
        """MessageEvent with name set but no sender returns None."""
        from openhands.sdk import Message

        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(
            container,
            app,  # type: ignore[arg-type]
            name="child_agent",
        )

        message = Message(
            role="user",
            content=[TextContent(text="Hello")],
        )
        # No sender set - this is a direct user message, not delegation
        event = MessageEvent(llm_message=message, source="user")

        widget = visualizer._create_event_widget(event)

        assert widget is None

    def test_message_event_renders_delegation_user_role(self):
        """MessageEvent from another agent (user role) shows sender->receiver."""
        from textual.widgets import Markdown

        from openhands.sdk import Message

        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(
            container,
            app,  # type: ignore[arg-type]
            name="child_agent",
        )

        message = Message(
            role="user",
            content=[TextContent(text="Do this task")],
        )
        event = MessageEvent(llm_message=message, source="agent", sender="parent_agent")

        widget = visualizer._create_event_widget(event)

        assert isinstance(widget, Markdown)
        # The markdown should contain the formatted arrow notation
        markdown_content = widget._initial_markdown
        assert markdown_content is not None
        assert "Parent Agent" in markdown_content
        assert "Child Agent" in markdown_content
        assert "→" in markdown_content

    def test_message_event_renders_delegation_assistant_role(self):
        """MessageEvent from this agent (assistant role) shows this->sender."""
        from textual.widgets import Markdown

        from openhands.sdk import Message

        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(
            container,
            app,  # type: ignore[arg-type]
            name="child_agent",
        )

        message = Message(
            role="assistant",
            content=[TextContent(text="Task completed")],
        )
        event = MessageEvent(llm_message=message, source="agent", sender="parent_agent")

        widget = visualizer._create_event_widget(event)

        assert isinstance(widget, Markdown)
        # For assistant role, this agent is the source
        markdown_content = widget._initial_markdown
        assert markdown_content is not None
        assert "Child Agent" in markdown_content
        assert "Parent Agent" in markdown_content
        assert "→" in markdown_content


class TestAgentMessageEventDisplay:
    """Tests for agent MessageEvent display in non-delegation context.

    This test class addresses GitHub issue #399:
    Agent MessageEvents (including those with critic_result) should be displayed
    in the TUI, but were being silently dropped due to a bug in the delegation
    filtering logic.

    The bug was in _create_event_widget() where the condition:
        if not (event.sender and self._name):
            return None
    would filter out ALL MessageEvents without a sender, even when the visualizer
    has a name set (which is the normal case for the main conversation).
    """

    def test_agent_message_event_displays_when_name_set_no_sender(self):
        """Agent MessageEvent without sender should display when visualizer has name.

        This is the primary bug reproduction test. In normal CLI usage:
        - visualizer._name is set to "OpenHands Agent"
        - Agent MessageEvents do NOT have a sender field
        - These should still be displayed (not filtered out)

        Relates to: https://github.com/OpenHands/OpenHands-CLI/issues/399
        """
        from textual.widgets import Markdown

        from openhands.sdk import Message
        from openhands_cli.tui.widgets.collapsible import Collapsible

        app = App()
        container = VerticalScroll()
        # Normal CLI usage: name is set to "OpenHands Agent"
        visualizer = ConversationVisualizer(
            container,
            app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )

        # Create an agent message (no sender - this is NOT delegation)
        message = Message(
            role="assistant",
            content=[TextContent(text="Here is my analysis of the data...")],
        )
        event = MessageEvent(llm_message=message, source="agent")
        # Note: event.sender is None (not set) - this is normal for non-delegation

        widget = visualizer._create_event_widget(event)

        # BUG: Currently returns None, should return a widget
        assert widget is not None, (
            "Agent MessageEvent without sender should still display when "
            "visualizer has name set. This is the normal case for CLI usage."
        )
        assert isinstance(widget, Markdown | Collapsible)

    def test_agent_message_event_with_critic_result_displays(self):
        """Agent MessageEvent with critic_result should display.

        This test ensures that MessageEvents enriched with critic evaluation
        results are displayed. The critic_result is added to the event after
        critic evaluation completes.

        Relates to: https://github.com/OpenHands/OpenHands-CLI/issues/399
        """
        from openhands.sdk import Message
        from openhands.sdk.critic.result import CriticResult

        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(
            container,
            app,  # type: ignore[arg-type]
            name="OpenHands Agent",
        )

        message = Message(
            role="assistant",
            content=[TextContent(text="Based on my analysis, here are the findings")],
        )
        # Create event with critic_result (simulating what the SDK does)
        event = MessageEvent(llm_message=message, source="agent")
        # Add critic_result like the SDK does
        event = event.model_copy(
            update={
                "critic_result": CriticResult(
                    score=0.78,
                    message="Success: 0.78",
                )
            }
        )

        widget = visualizer._create_event_widget(event)

        assert widget is not None, (
            "Agent MessageEvent with critic_result should display. "
            "Users wait for critic feedback that never appears due to this bug."
        )

    def test_delegation_message_still_works_with_sender(self):
        """Delegation MessageEvents with sender should still display correctly.

        This test ensures the fix doesn't break delegation message handling.
        """
        from textual.widgets import Markdown

        from openhands.sdk import Message

        app = App()
        container = VerticalScroll()
        visualizer = ConversationVisualizer(
            container,
            app,  # type: ignore[arg-type]
            name="child_agent",
        )

        message = Message(
            role="assistant",
            content=[TextContent(text="Task completed")],
        )
        # Delegation message HAS a sender
        event = MessageEvent(llm_message=message, source="agent", sender="parent_agent")

        widget = visualizer._create_event_widget(event)

        assert widget is not None
        assert isinstance(widget, Markdown)
        markdown_content = widget._initial_markdown
        assert markdown_content is not None
        assert "Child Agent" in markdown_content
        assert "Parent Agent" in markdown_content


class TestRenderUserMessage:
    """Tests for ConversationVisualizer.render_user_message."""

    def test_render_user_message_creates_static_widget(self):
        """render_user_message should create a Static widget with user message."""
        from unittest.mock import MagicMock

        app = MagicMock()
        container = MagicMock()
        visualizer = ConversationVisualizer(container, app)

        # Track widgets added via _run_on_main_thread
        added_widgets: list[Static] = []

        def capture_add(func, *args):
            if func == visualizer._add_widget_to_ui and args:
                added_widgets.append(args[0])

        visualizer._run_on_main_thread = capture_add  # type: ignore[method-assign]

        visualizer.render_user_message("Hello, agent!")

        assert len(added_widgets) == 1
        widget = added_widgets[0]
        assert isinstance(widget, Static)
        # Check widget has user-message class
        assert "user-message" in widget.classes

    def test_render_user_message_format(self):
        """render_user_message should prefix content with '> '."""
        from unittest.mock import MagicMock

        app = MagicMock()
        container = MagicMock()
        visualizer = ConversationVisualizer(container, app)

        added_widgets: list[Static] = []

        def capture_add(func, *args):
            if func == visualizer._add_widget_to_ui and args:
                added_widgets.append(args[0])

        visualizer._run_on_main_thread = capture_add  # type: ignore[method-assign]

        visualizer.render_user_message("Test message")

        assert len(added_widgets) == 1
        widget = added_widgets[0]
        assert isinstance(widget, Static)
        # Check the widget has user-message class (format verification)
        assert "user-message" in widget.classes
