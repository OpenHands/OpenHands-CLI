"""Tests for confirmation panel functionality."""

from unittest import mock

import pytest
from textual.app import App
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import ListView, Static

from openhands_cli.tui.panels.confirmation_panel import (
    ConfirmationPanel,
    ConfirmationSidePanel,
)
from openhands_cli.user_actions.types import UserConfirmation


class MockActionObject:
    """Mock action object with visualize attribute."""

    def __init__(self, text: str):
        """Initialize mock action object."""
        self.visualize = text


class MockActionEvent:
    """Mock ActionEvent for testing.

    This provides the minimal interface used by ConfirmationPanel:
    - tool_name: str
    - action: object with visualize attribute (or None)
    """

    def __init__(self, tool_name: str = "unknown", action_text: str = ""):
        """Initialize mock action event."""
        self.tool_name = tool_name
        self.action = MockActionObject(action_text) if action_text else None


class TestConfirmationPanelLayout:
    """Tests for the ConfirmationPanel layout structure using async app context."""

    @pytest.mark.asyncio
    async def test_panel_has_header(self):
        """Test that the panel has a header with action count."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        class TestApp(App):
            def compose(self):
                yield ConfirmationPanel(
                    pending_actions=actions,  # type: ignore[arg-type]
                    confirmation_callback=callback,
                )

        app = TestApp()

        async with app.run_test() as pilot:
            # Query for the header
            headers = pilot.app.query(".confirmation-header")
            assert len(headers) == 1
            assert isinstance(headers[0], Static)

    @pytest.mark.asyncio
    async def test_panel_has_actions_container(self):
        """Test that the panel has a container for actions."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        class TestApp(App):
            def compose(self):
                yield ConfirmationPanel(
                    pending_actions=actions,  # type: ignore[arg-type]
                    confirmation_callback=callback,
                )

        app = TestApp()

        async with app.run_test() as pilot:
            # Query for the actions container
            actions_containers = pilot.app.query(".actions-container")
            assert len(actions_containers) == 1
            assert isinstance(actions_containers[0], Container)

    @pytest.mark.asyncio
    async def test_panel_has_confirmation_content(self):
        """Test that the panel has a vertical content container."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        class TestApp(App):
            def compose(self):
                yield ConfirmationPanel(
                    pending_actions=actions,  # type: ignore[arg-type]
                    confirmation_callback=callback,
                )

        app = TestApp()

        async with app.run_test() as pilot:
            # Query for the content container
            content = pilot.app.query(".confirmation-content")
            assert len(content) == 1
            assert isinstance(content[0], Vertical)

    @pytest.mark.asyncio
    async def test_panel_has_listview_with_options(self):
        """Test that the panel has a ListView with confirmation options."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        class TestApp(App):
            def compose(self):
                yield ConfirmationPanel(
                    pending_actions=actions,  # type: ignore[arg-type]
                    confirmation_callback=callback,
                )

        app = TestApp()

        async with app.run_test() as pilot:
            # Query for the ListView
            listview = pilot.app.query_one("#confirmation-listview", ListView)
            assert listview is not None


class TestConfirmationPanelCallbacks:
    """Tests for confirmation panel callback handling."""

    def test_accept_callback(self):
        """Test that selecting 'accept' triggers the correct callback."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        panel = ConfirmationPanel(
            pending_actions=actions,  # type: ignore[arg-type]
            confirmation_callback=callback,
        )

        # Create a mock ListView.Selected event
        mock_item = mock.MagicMock()
        mock_item.id = "accept"
        mock_event = mock.MagicMock()
        mock_event.item = mock_item

        # Trigger the selection handler
        panel.on_list_view_selected(mock_event)

        callback.assert_called_once_with(UserConfirmation.ACCEPT)

    def test_reject_callback(self):
        """Test that selecting 'reject' triggers the correct callback."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        panel = ConfirmationPanel(
            pending_actions=actions,  # type: ignore[arg-type]
            confirmation_callback=callback,
        )

        # Create a mock ListView.Selected event
        mock_item = mock.MagicMock()
        mock_item.id = "reject"
        mock_event = mock.MagicMock()
        mock_event.item = mock_item

        # Trigger the selection handler
        panel.on_list_view_selected(mock_event)

        callback.assert_called_once_with(UserConfirmation.REJECT)

    def test_always_proceed_callback(self):
        """Test that selecting 'always' triggers the correct callback."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        panel = ConfirmationPanel(
            pending_actions=actions,  # type: ignore[arg-type]
            confirmation_callback=callback,
        )

        # Create a mock ListView.Selected event
        mock_item = mock.MagicMock()
        mock_item.id = "always"
        mock_event = mock.MagicMock()
        mock_event.item = mock_item

        # Trigger the selection handler
        panel.on_list_view_selected(mock_event)

        callback.assert_called_once_with(UserConfirmation.ALWAYS_PROCEED)

    def test_risky_callback(self):
        """Test that selecting 'risky' triggers the correct callback."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        panel = ConfirmationPanel(
            pending_actions=actions,  # type: ignore[arg-type]
            confirmation_callback=callback,
        )

        # Create a mock ListView.Selected event
        mock_item = mock.MagicMock()
        mock_item.id = "risky"
        mock_event = mock.MagicMock()
        mock_event.item = mock_item

        # Trigger the selection handler
        panel.on_list_view_selected(mock_event)

        callback.assert_called_once_with(UserConfirmation.CONFIRM_RISKY)


class TestConfirmationPanelWithLongContent:
    """Tests for confirmation panel with long content (the main fix)."""

    @pytest.mark.asyncio
    async def test_panel_structure_supports_scrolling(self):
        """Test that the panel structure supports scrolling for long content."""
        callback = mock.MagicMock()

        # Create actions with very long content
        long_content = "x" * 5000  # Very long content
        actions = [MockActionEvent("file_editor", long_content)]

        class TestApp(App):
            def compose(self):
                yield ConfirmationPanel(
                    pending_actions=actions,  # type: ignore[arg-type]
                    confirmation_callback=callback,
                )

        app = TestApp()

        async with app.run_test() as pilot:
            # Verify structure: header, actions container, instructions, listview
            headers = pilot.app.query(".confirmation-header")
            assert len(headers) == 1
            assert isinstance(headers[0], Static)

            # Actions should be in a container
            actions_containers = pilot.app.query(".actions-container")
            assert len(actions_containers) == 1
            assert isinstance(actions_containers[0], Container)

            # Instructions should be present
            instructions = pilot.app.query(".confirmation-instructions")
            assert len(instructions) == 1
            assert isinstance(instructions[0], Static)

            # ListView should be present
            listview = pilot.app.query_one("#confirmation-listview", ListView)
            assert listview is not None

    @pytest.mark.asyncio
    async def test_multiple_long_actions_in_container(self):
        """Test that multiple long actions are placed in the actions container."""
        callback = mock.MagicMock()

        # Create multiple actions with long content
        long_content = "y" * 1000
        actions = [
            MockActionEvent("file_editor", long_content),
            MockActionEvent("execute_bash", long_content),
            MockActionEvent("str_replace_editor", long_content),
        ]

        class TestApp(App):
            def compose(self):
                yield ConfirmationPanel(
                    pending_actions=actions,  # type: ignore[arg-type]
                    confirmation_callback=callback,
                )

        app = TestApp()

        async with app.run_test() as pilot:
            # Get the actions container
            actions_container = pilot.app.query_one(".actions-container", Container)
            assert actions_container is not None

            # The container should have action items
            action_items = pilot.app.query(".action-item")
            assert len(action_items) == 3  # 3 actions


class TestConfirmationSidePanel:
    """Tests for the ConfirmationSidePanel container."""

    def test_side_panel_is_vertical_scroll(self):
        """Test that ConfirmationSidePanel is a VerticalScroll for scrolling."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        side_panel = ConfirmationSidePanel(
            pending_actions=actions,  # type: ignore[arg-type]
            confirmation_callback=callback,
        )

        # ConfirmationSidePanel should be a VerticalScroll for scrolling
        assert isinstance(side_panel, VerticalScroll)

    def test_side_panel_contains_confirmation_panel(self):
        """Test that ConfirmationSidePanel contains a ConfirmationPanel."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        side_panel = ConfirmationSidePanel(
            pending_actions=actions,  # type: ignore[arg-type]
            confirmation_callback=callback,
        )

        # Compose the side panel
        children = list(side_panel.compose())

        # Should contain exactly one ConfirmationPanel
        assert len(children) == 1
        assert isinstance(children[0], ConfirmationPanel)


class TestConfirmationPanelIntegration:
    """Integration tests for the confirmation panel in a Textual app."""

    @pytest.mark.asyncio
    async def test_panel_renders_in_app(self):
        """Test that the confirmation panel renders correctly in a Textual app."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        class TestApp(App):
            def compose(self):
                yield ConfirmationSidePanel(
                    pending_actions=actions,  # type: ignore[arg-type]
                    confirmation_callback=callback,
                )

        app = TestApp()

        async with app.run_test() as pilot:
            # Verify the panel is rendered
            side_panel = pilot.app.query_one(ConfirmationSidePanel)
            assert side_panel is not None

            # Verify the inner panel exists
            inner_panel = pilot.app.query_one(ConfirmationPanel)
            assert inner_panel is not None

            # Verify the ListView exists
            listview = pilot.app.query_one("#confirmation-listview", ListView)
            assert listview is not None

    @pytest.mark.asyncio
    async def test_panel_with_long_content_is_scrollable(self):
        """Test that panel with long content is scrollable via ConfirmationSidePanel."""
        callback = mock.MagicMock()

        # Create action with very long content
        long_content = "z" * 5000
        actions = [MockActionEvent("file_editor", long_content)]

        class TestApp(App):
            def compose(self):
                yield ConfirmationSidePanel(
                    pending_actions=actions,  # type: ignore[arg-type]
                    confirmation_callback=callback,
                )

        app = TestApp()

        async with app.run_test() as pilot:
            # Verify the side panel is a VerticalScroll (scrollable)
            side_panel = pilot.app.query_one(ConfirmationSidePanel)
            assert side_panel is not None
            assert isinstance(side_panel, VerticalScroll)

            # Verify the actions container exists
            actions_container = pilot.app.query_one(".actions-container")
            assert actions_container is not None

            # Verify the ListView exists (buttons should be scrollable to)
            listview = pilot.app.query_one("#confirmation-listview", ListView)
            assert listview is not None

    @pytest.mark.asyncio
    async def test_listview_is_focusable(self):
        """Test that the ListView can receive focus for keyboard navigation."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        class TestApp(App):
            def compose(self):
                yield ConfirmationSidePanel(
                    pending_actions=actions,  # type: ignore[arg-type]
                    confirmation_callback=callback,
                )

        app = TestApp()

        async with app.run_test() as pilot:
            # Get the ListView
            listview = pilot.app.query_one("#confirmation-listview", ListView)

            # Verify it can be focused
            assert listview.can_focus

    @pytest.mark.asyncio
    async def test_keyboard_selection_triggers_callback(self):
        """Test that keyboard selection triggers the callback."""
        callback = mock.MagicMock()
        actions = [MockActionEvent("test_tool", "test action")]

        class TestApp(App):
            def compose(self):
                yield ConfirmationSidePanel(
                    pending_actions=actions,  # type: ignore[arg-type]
                    confirmation_callback=callback,
                )

        app = TestApp()

        async with app.run_test() as pilot:
            # Get the ListView and focus it
            listview = pilot.app.query_one("#confirmation-listview", ListView)
            listview.focus()

            # Press Enter to select the first item (accept)
            await pilot.press("enter")

            # Verify the callback was called with ACCEPT
            callback.assert_called_once_with(UserConfirmation.ACCEPT)
