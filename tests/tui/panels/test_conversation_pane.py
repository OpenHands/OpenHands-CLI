"""Tests for ConversationPane and LoadMoreButton."""

import uuid
from unittest.mock import Mock

import pytest
from textual.app import App
from textual.widgets import Static

from openhands_cli.tui.panels.conversation_pane import (
    ConversationPane,
    LoadMoreButton,
)


def make_test_app(widget):
    """Create a test app with the given widget."""

    class TestApp(App):
        def compose(self):
            yield widget

    return TestApp()


class TestConversationPaneInit:
    """Tests for ConversationPane initialization."""

    def test_init_stores_conversation_id(self):
        """Pane should store the conversation ID."""
        conv_id = uuid.uuid4()
        pane = ConversationPane(conv_id)

        assert pane.conversation_id == conv_id

    def test_init_is_not_rendered_by_default(self):
        """Pane should not be marked as rendered initially."""
        pane = ConversationPane(uuid.uuid4())

        assert pane.is_rendered is False

    def test_init_show_header_default_false(self):
        """Header should be hidden by default."""
        pane = ConversationPane(uuid.uuid4())

        assert pane._show_header is False

    def test_init_show_header_true(self):
        """Header can be shown on init."""
        pane = ConversationPane(uuid.uuid4(), show_header=True)

        assert pane._show_header is True


class TestConversationPaneProperties:
    """Tests for ConversationPane properties."""

    def test_content_container_returns_self(self):
        """content_container should return the pane itself."""
        pane = ConversationPane(uuid.uuid4())

        assert pane.content_container is pane

    def test_has_more_history_delegates_to_manager(self):
        """has_more_history should delegate to history manager."""
        pane = ConversationPane(uuid.uuid4())
        # Initialize with more events than page size (default 20)
        # so has_more returns True
        pane._conversation_history_manager.reset([Mock() for _ in range(25)])

        assert pane.has_more_history is True


class TestConversationPaneMarkAsActive:
    """Tests for mark_as_active method."""

    def test_mark_as_active_sets_is_rendered(self):
        """mark_as_active should set _is_rendered to True."""
        pane = ConversationPane(uuid.uuid4())

        pane.mark_as_active()

        assert pane.is_rendered is True

    @pytest.mark.asyncio
    async def test_mark_as_active_prevents_duplicate_rendering(self):
        """After mark_as_active, render_history should skip rendering."""
        pane = ConversationPane(uuid.uuid4())
        app = make_test_app(pane)

        async with app.run_test():
            pane.mark_as_active()

            # Create a mock visualizer
            mock_visualizer = Mock()
            events = [Mock() for _ in range(3)]

            # render_history should skip because already marked as active
            pane.render_history(events, mock_visualizer)

            # on_event should NOT have been called
            mock_visualizer.on_event.assert_not_called()


class TestConversationPaneCompose:
    """Tests for ConversationPane compose (requires app context)."""

    @pytest.mark.asyncio
    async def test_compose_creates_header_widget(self):
        """compose should create a header Static widget."""
        pane = ConversationPane(uuid.uuid4())
        app = make_test_app(pane)

        async with app.run_test() as pilot:
            header = pilot.app.query_one(f"#{ConversationPane.ID_HEADER}", Static)
            assert header is not None

    @pytest.mark.asyncio
    async def test_header_hidden_by_default(self):
        """Header should have pane-header class but not visible class by default."""
        pane = ConversationPane(uuid.uuid4(), show_header=False)
        app = make_test_app(pane)

        async with app.run_test() as pilot:
            header = pilot.app.query_one(f"#{ConversationPane.ID_HEADER}", Static)
            assert ConversationPane.CLASS_PANE_HEADER in header.classes
            assert ConversationPane.CLASS_VISIBLE not in header.classes

    @pytest.mark.asyncio
    async def test_header_visible_when_show_header_true(self):
        """Header should have visible class when show_header=True."""
        pane = ConversationPane(uuid.uuid4(), show_header=True)
        app = make_test_app(pane)

        async with app.run_test() as pilot:
            header = pilot.app.query_one(f"#{ConversationPane.ID_HEADER}", Static)
            assert ConversationPane.CLASS_VISIBLE in header.classes


class TestConversationPaneSetHeaderVisible:
    """Tests for set_header_visible method."""

    @pytest.mark.asyncio
    async def test_set_header_visible_adds_class(self):
        """set_header_visible(True) should add visible class."""
        pane = ConversationPane(uuid.uuid4(), show_header=False)
        app = make_test_app(pane)

        async with app.run_test() as pilot:
            pane.set_header_visible(True)
            header = pilot.app.query_one(f"#{ConversationPane.ID_HEADER}", Static)
            assert ConversationPane.CLASS_VISIBLE in header.classes

    @pytest.mark.asyncio
    async def test_set_header_visible_removes_class(self):
        """set_header_visible(False) should remove visible class."""
        pane = ConversationPane(uuid.uuid4(), show_header=True)
        app = make_test_app(pane)

        async with app.run_test() as pilot:
            pane.set_header_visible(False)
            header = pilot.app.query_one(f"#{ConversationPane.ID_HEADER}", Static)
            assert ConversationPane.CLASS_VISIBLE not in header.classes

    @pytest.mark.asyncio
    async def test_set_header_visible_updates_internal_state(self):
        """set_header_visible should update _show_header."""
        pane = ConversationPane(uuid.uuid4(), show_header=False)
        app = make_test_app(pane)

        async with app.run_test():
            pane.set_header_visible(True)
            assert pane._show_header is True

            pane.set_header_visible(False)
            assert pane._show_header is False


class TestConversationPaneRenderHistory:
    """Tests for render_history method (requires app context)."""

    @pytest.mark.asyncio
    async def test_render_history_sets_is_rendered(self):
        """render_history should set _is_rendered to True."""
        pane = ConversationPane(uuid.uuid4())
        app = make_test_app(pane)

        async with app.run_test():
            mock_visualizer = Mock()
            # Call with empty events (simpler test)
            pane.render_history([], mock_visualizer)

            assert pane.is_rendered is True

    @pytest.mark.asyncio
    async def test_render_history_skips_if_already_rendered(self):
        """render_history should skip if already rendered."""
        pane = ConversationPane(uuid.uuid4())
        app = make_test_app(pane)

        async with app.run_test():
            pane._is_rendered = True

            mock_visualizer = Mock()
            events = [Mock() for _ in range(3)]

            result = pane.render_history(events, mock_visualizer)

            # Should return visualizer without calling on_event
            assert result is mock_visualizer
            mock_visualizer.on_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_render_history_returns_visualizer(self):
        """render_history should return the visualizer."""
        pane = ConversationPane(uuid.uuid4())
        app = make_test_app(pane)

        async with app.run_test():
            mock_visualizer = Mock()
            result = pane.render_history([], mock_visualizer)

            assert result is mock_visualizer


class TestConversationPaneCSS:
    """Tests for CSS class constants."""

    def test_css_class_constants_defined(self):
        """CSS class constants should be defined."""
        assert ConversationPane.CLASS_PANE_HEADER == "pane-header"
        assert ConversationPane.CLASS_VISIBLE == "visible"
        assert ConversationPane.ID_HEADER == "pane_conversation_header"
        assert ConversationPane.ID_LOAD_MORE == "load_more_button"


class TestLoadMoreButton:
    """Tests for LoadMoreButton widget."""

    def test_format_label_with_remaining(self):
        """Button label should include remaining count."""
        button = LoadMoreButton(remaining=10)
        assert "10 remaining" in str(button.label)

    def test_format_label_without_remaining(self):
        """Button label should work without remaining count."""
        button = LoadMoreButton(remaining=0)
        assert "Load more history" in str(button.label)
        assert "remaining" not in str(button.label)

    def test_update_remaining_updates_label(self):
        """update_remaining should update the label."""
        button = LoadMoreButton(remaining=5)
        button.update_remaining(15)
        assert "15 remaining" in str(button.label)

    @pytest.mark.asyncio
    async def test_button_hidden_when_no_remaining(self):
        """Button should be hidden when remaining is 0."""
        button = LoadMoreButton(remaining=5, id="test_btn")

        class TestApp(App):
            def compose(self):
                yield button

        app = TestApp()
        async with app.run_test():
            button.update_remaining(0)
            assert "-hidden" in button.classes

    @pytest.mark.asyncio
    async def test_button_visible_when_has_remaining(self):
        """Button should be visible when remaining > 0."""
        button = LoadMoreButton(remaining=0, id="test_btn", classes="-hidden")

        class TestApp(App):
            def compose(self):
                yield button

        app = TestApp()
        async with app.run_test():
            button.update_remaining(10)
            assert "-hidden" not in button.classes


class TestConversationPaneLoadMore:
    """Tests for Load More button in ConversationPane."""

    @pytest.mark.asyncio
    async def test_compose_creates_load_more_button(self):
        """compose should create a Load More button widget."""
        pane = ConversationPane(uuid.uuid4())
        app = make_test_app(pane)

        async with app.run_test() as pilot:
            button = pilot.app.query_one(
                f"#{ConversationPane.ID_LOAD_MORE}", LoadMoreButton
            )
            assert button is not None

    @pytest.mark.asyncio
    async def test_load_more_button_hidden_by_default(self):
        """Load More button should be hidden by default."""
        pane = ConversationPane(uuid.uuid4())
        app = make_test_app(pane)

        async with app.run_test() as pilot:
            button = pilot.app.query_one(
                f"#{ConversationPane.ID_LOAD_MORE}", LoadMoreButton
            )
            assert "-hidden" in button.classes

    @pytest.mark.asyncio
    async def test_render_history_updates_load_more_visibility(self):
        """render_history should update Load More button visibility."""
        pane = ConversationPane(uuid.uuid4())
        app = make_test_app(pane)

        async with app.run_test() as pilot:
            # Provide enough events to have more history (page_size=5 by default)
            mock_visualizer = Mock()
            events = [Mock() for _ in range(10)]
            pane.render_history(events, mock_visualizer)

            button = pilot.app.query_one(
                f"#{ConversationPane.ID_LOAD_MORE}", LoadMoreButton
            )
            # Should be visible because there are remaining events
            assert "-hidden" not in button.classes
