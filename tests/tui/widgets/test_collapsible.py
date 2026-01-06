from unittest.mock import MagicMock, patch

import pyperclip
import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.widgets.collapsible import (
    Collapsible,
    CollapsibleNavigationMixin,
    CollapsibleTitle,
)


class CollapsibleTestApp(App):
    """Minimal Textual App that mounts a single Collapsible."""

    def __init__(self, collapsible: Collapsible) -> None:
        super().__init__()
        self.collapsible = collapsible
        self.register_theme(OPENHANDS_THEME)
        self.theme = "openhands"

    def compose(self) -> ComposeResult:
        yield self.collapsible


@pytest.mark.asyncio
async def test_collapsible_initial_render() -> None:
    """Collapsible in collapsed state
    renders collapsed symbol + label in title."""

    collapsible = Collapsible(
        "some content",
        title="My Section",
        collapsed=True,
        collapsed_symbol="▶",
        expanded_symbol="▼",
        border_color="red",
    )

    app = CollapsibleTestApp(collapsible)

    async with app.run_test() as _pilot:
        title_widget = collapsible.query_one(CollapsibleTitle)
        title_static = title_widget.query_one(Static)

        # Renderable is usually a Rich object; stringify for a robust check
        rendered = str(title_static.content)
        assert "▶" in rendered
        assert "My Section" in rendered


@pytest.mark.asyncio
async def test_toggle_updates_title_and_css_class() -> None:
    """Toggling collapsed updates the '-collapsed'
    CSS class and title.collapsed state."""

    collapsible = Collapsible(
        "some content", title="Title", collapsed=True, border_color="red"
    )

    app = CollapsibleTestApp(collapsible)

    async with app.run_test() as _pilot:
        # Initially collapsed
        assert collapsible.collapsed is True
        assert collapsible.has_class("-collapsed")
        assert collapsible._title.collapsed is True
        assert collapsible._title._title_static is not None

        # Toggle to expanded
        collapsible.collapsed = False
        await _pilot.pause()  # give Textual a tick if needed

        assert collapsible.collapsed is False
        assert not collapsible.has_class("-collapsed")
        assert collapsible._title.collapsed is False
        title_static = collapsible._title._title_static
        assert "▼" in str(title_static.content)


@pytest.mark.asyncio
async def test_content_copies_and_shows_success_notification() -> None:
    """Copy handler copies _content_string
    to clipboard and shows success notification."""

    collapsible = Collapsible(
        "content to copy", title="Title", collapsed=True, border_color="red"
    )

    app = CollapsibleTestApp(collapsible)

    # Patch pyperclip.copy in the correct module
    with patch("openhands_cli.tui.widgets.collapsible.pyperclip.copy") as mock_copy:
        async with app.run_test() as _pilot:
            # Replace notify with a MagicMock so we can assert on it
            app.notify = MagicMock()

            event = CollapsibleTitle.CopyRequested()
            collapsible._on_collapsible_title_copy_requested(event)

            # pyperclip.copy should receive the stringified content
            mock_copy.assert_called_once_with("content to copy")

            # app.notify should be called with a success message
            app.notify.assert_called_once()
            args, kwargs = app.notify.call_args
            assert "Content copied to clipboard" in args[0]
            assert kwargs.get("title") == "Copy Success"
            # No error severity when copy succeeds
            assert kwargs.get("severity") in (None, "info")


@pytest.mark.asyncio
async def test_copy_handler_handles_empty_content_with_warning() -> None:
    """Copy handler shows a warning and does
    not call pyperclip when there's no content."""

    collapsible = Collapsible(
        "",  # empty content
        title="Empty",
        collapsed=True,
        border_color="red",
    )

    # Explicitly clear _content_string to simulate no content
    collapsible._content_string = ""

    app = CollapsibleTestApp(collapsible)

    with patch("openhands_cli.tui.widgets.collapsible.pyperclip.copy") as mock_copy:
        async with app.run_test() as _pilot:
            app.notify = MagicMock()

            event = CollapsibleTitle.CopyRequested()
            collapsible._on_collapsible_title_copy_requested(event)

            # No clipboard interaction when empty
            mock_copy.assert_not_called()

            # Warning notification is shown
            app.notify.assert_called_once()
            args, kwargs = app.notify.call_args
            assert "No content to copy" in args[0]
            assert kwargs.get("title") == "Copy Warning"
            assert kwargs.get("severity") == "warning"


@pytest.mark.asyncio
async def test_copy_button_click_triggers_copy() -> None:
    """Clicking the copy button triggers the copy mechanism."""

    collapsible = Collapsible(
        "button click content", title="Title", collapsed=True, border_color="red"
    )

    app = CollapsibleTestApp(collapsible)

    # Patch pyperclip.copy in the correct module
    with patch("openhands_cli.tui.widgets.collapsible.pyperclip.copy") as mock_copy:
        async with app.run_test() as pilot:
            # Replace notify with a MagicMock so we can assert on it
            app.notify = MagicMock()

            # Find and click the copy button
            copy_button = collapsible.query_one("#copy-btn", Button)
            await pilot.click(copy_button)

            # pyperclip.copy should receive the stringified content
            mock_copy.assert_called_once_with("button click content")

            # app.notify should be called with a success message
            app.notify.assert_called_once()
            args, kwargs = app.notify.call_args
            assert "Content copied to clipboard" in args[0]
            assert kwargs.get("title") == "Copy Success"


@pytest.mark.asyncio
async def test_copy_on_linux_without_pyperclip_shows_xclip_hint() -> None:
    """When pyperclip fails on Linux, message includes xclip install hint."""

    collapsible = Collapsible(
        "content to copy", title="Title", collapsed=True, border_color="red"
    )

    app = CollapsibleTestApp(collapsible)

    # Patch pyperclip.copy to raise PyperclipException (simulating missing xclip)
    # Patch _is_linux to return True
    with (
        patch(
            "openhands_cli.tui.widgets.collapsible.pyperclip.copy",
            side_effect=pyperclip.PyperclipException(
                "No clipboard mechanism available"
            ),
        ),
        patch(
            "openhands_cli.tui.widgets.collapsible._is_linux",
            return_value=True,
        ),
    ):
        async with app.run_test() as _pilot:
            # Replace notify with a MagicMock so we can assert on it
            app.notify = MagicMock()
            # Mock copy_to_clipboard (OSC 52 doesn't raise, just sends escape sequences)
            app.copy_to_clipboard = MagicMock()

            event = CollapsibleTitle.CopyRequested()
            collapsible._on_collapsible_title_copy_requested(event)

            # copy_to_clipboard should still be called (OSC 52 fallback)
            app.copy_to_clipboard.assert_called_once_with("content to copy")

            # app.notify should be called with hint about xclip
            app.notify.assert_called_once()
            args, kwargs = app.notify.call_args
            assert "Copy attempted" in args[0]
            assert "sudo apt install xclip" in args[0]
            assert kwargs.get("title") == "Copy"


@pytest.mark.asyncio
async def test_copy_on_non_linux_without_pyperclip_shows_success() -> None:
    """When pyperclip fails on non-Linux, shows success (OSC 52 likely works)."""

    collapsible = Collapsible(
        "content to copy", title="Title", collapsed=True, border_color="red"
    )

    app = CollapsibleTestApp(collapsible)

    # Patch pyperclip.copy to raise PyperclipException
    # Patch _is_linux to return False (e.g., macOS or Windows)
    with (
        patch(
            "openhands_cli.tui.widgets.collapsible.pyperclip.copy",
            side_effect=pyperclip.PyperclipException(
                "No clipboard mechanism available"
            ),
        ),
        patch(
            "openhands_cli.tui.widgets.collapsible._is_linux",
            return_value=False,
        ),
    ):
        async with app.run_test() as _pilot:
            # Replace notify with a MagicMock so we can assert on it
            app.notify = MagicMock()
            # Mock copy_to_clipboard (OSC 52 doesn't raise, just sends escape sequences)
            app.copy_to_clipboard = MagicMock()

            event = CollapsibleTitle.CopyRequested()
            collapsible._on_collapsible_title_copy_requested(event)

            # copy_to_clipboard should still be called (OSC 52 fallback)
            app.copy_to_clipboard.assert_called_once_with("content to copy")

            # app.notify should show success (no xclip hint on non-Linux)
            app.notify.assert_called_once()
            args, kwargs = app.notify.call_args
            assert "Content copied to clipboard" in args[0]
            assert "xclip" not in args[0]
            assert kwargs.get("title") == "Copy Success"


class MultiCollapsibleTestApp(CollapsibleNavigationMixin, App):
    """App with multiple collapsibles for testing navigation.

    Uses CollapsibleNavigationMixin to share the same navigation logic
    as the main OpenHandsApp, ensuring tests verify the real behavior.
    """

    def __init__(self) -> None:
        super().__init__()
        self.register_theme(OPENHANDS_THEME)
        self.theme = "openhands"

    def compose(self) -> ComposeResult:
        from textual.containers import VerticalScroll

        with VerticalScroll(id="main_display"):
            yield Collapsible(
                "Content 1", title="Cell 1", collapsed=True, border_color="red"
            )
            yield Collapsible(
                "Content 2", title="Cell 2", collapsed=True, border_color="blue"
            )
            yield Collapsible(
                "Content 3", title="Cell 3", collapsed=True, border_color="green"
            )


@pytest.mark.asyncio
async def test_arrow_key_navigation_down() -> None:
    """Down arrow navigates to the next cell."""
    app = MultiCollapsibleTestApp()

    async with app.run_test() as pilot:
        # Get all collapsibles
        collapsibles = list(app.query(Collapsible))
        assert len(collapsibles) == 3

        # Focus the first cell's title
        first_title = collapsibles[0].query_one(CollapsibleTitle)
        first_title.focus()
        await pilot.pause()
        assert app.focused == first_title

        # Press down arrow - should focus second cell
        await pilot.press("down")
        second_title = collapsibles[1].query_one(CollapsibleTitle)
        assert app.focused == second_title


@pytest.mark.asyncio
async def test_arrow_key_navigation_up() -> None:
    """Up arrow navigates to the previous cell."""
    app = MultiCollapsibleTestApp()

    async with app.run_test() as pilot:
        # Get all collapsibles
        collapsibles = list(app.query(Collapsible))

        # Focus the second cell's title
        second_title = collapsibles[1].query_one(CollapsibleTitle)
        second_title.focus()
        await pilot.pause()
        assert app.focused == second_title

        # Press up arrow - should focus first cell
        await pilot.press("up")
        first_title = collapsibles[0].query_one(CollapsibleTitle)
        assert app.focused == first_title


@pytest.mark.asyncio
async def test_arrow_navigation_at_boundaries() -> None:
    """Arrow keys at boundaries don't crash or change focus."""
    app = MultiCollapsibleTestApp()

    async with app.run_test() as pilot:
        collapsibles = list(app.query(Collapsible))

        # Focus the first cell and press up - should stay on first
        first_title = collapsibles[0].query_one(CollapsibleTitle)
        first_title.focus()
        await pilot.pause()
        await pilot.press("up")
        assert app.focused == first_title

        # Focus the last cell and press down - should stay on last
        last_title = collapsibles[2].query_one(CollapsibleTitle)
        last_title.focus()
        await pilot.pause()
        await pilot.press("down")
        assert app.focused == last_title


@pytest.mark.asyncio
async def test_enter_still_toggles_collapsible() -> None:
    """Enter key still toggles the collapsible state."""
    app = MultiCollapsibleTestApp()

    async with app.run_test() as pilot:
        collapsibles = list(app.query(Collapsible))
        first_collapsible = collapsibles[0]

        # Focus the first cell's title
        first_title = first_collapsible.query_one(CollapsibleTitle)
        first_title.focus()
        await pilot.pause()

        # Initially collapsed
        assert first_collapsible.collapsed is True

        # Press enter - should toggle to expanded
        await pilot.press("enter")
        await pilot.pause()
        assert first_collapsible.collapsed is False

        # Press enter again - should toggle back to collapsed
        await pilot.press("enter")
        await pilot.pause()
        assert first_collapsible.collapsed is True
