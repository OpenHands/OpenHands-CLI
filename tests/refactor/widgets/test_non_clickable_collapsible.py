from unittest.mock import MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from openhands_cli.refactor.widgets.non_clickable_collapsible import (
    NonClickableCollapsible,
    NonClickableCollapsibleTitle,
)
from openhands_cli.theme import OPENHANDS_THEME


class CollapsibleTestApp(App):
    """Minimal Textual App that mounts a single NonClickableCollapsible."""

    def __init__(self, collapsible: NonClickableCollapsible) -> None:
        super().__init__()
        self.collapsible = collapsible
        self.register_theme(OPENHANDS_THEME)
        self.theme = "openhands"

    def compose(self) -> ComposeResult:
        yield self.collapsible


@pytest.mark.asyncio
async def test_non_clickable_collapsible_initial_render() -> None:
    """NonClickableCollapsible in collapsed state
    renders collapsed symbol + label in title."""

    collapsible = NonClickableCollapsible(
        "some content",
        title="My Section",
        collapsed=True,
        collapsed_symbol="▶",
        expanded_symbol="▼",
        border_color="red",
    )

    app = CollapsibleTestApp(collapsible)

    async with app.run_test() as _pilot:
        title_widget = collapsible.query_one(NonClickableCollapsibleTitle)
        title_static = title_widget.query_one(Static)

        # Renderable is usually a Rich object; stringify for a robust check
        rendered = str(title_static.content)
        assert "▶" in rendered
        assert "My Section" in rendered


@pytest.mark.asyncio
async def test_toggle_updates_title_and_css_class() -> None:
    """Toggling collapsed updates the '-collapsed'
    CSS class and title.collapsed state."""

    collapsible = NonClickableCollapsible(
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

    collapsible = NonClickableCollapsible(
        "content to copy", title="Title", collapsed=True, border_color="red"
    )

    app = CollapsibleTestApp(collapsible)

    # Patch pyperclip.copy in the correct module
    with patch(
        "openhands_cli.refactor.widgets.non_clickable_collapsible.pyperclip.copy"
    ) as mock_copy:
        async with app.run_test() as _pilot:
            # Replace notify with a MagicMock so we can assert on it
            app.notify = MagicMock()

            event = NonClickableCollapsibleTitle.CopyRequested()
            collapsible._on_non_clickable_collapsible_title_copy_requested(event)

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

    collapsible = NonClickableCollapsible(
        "",  # empty content
        title="Empty",
        collapsed=True,
        border_color="red",
    )

    # Explicitly clear _content_string to simulate no content
    collapsible._content_string = ""

    app = CollapsibleTestApp(collapsible)

    with patch(
        "openhands_cli.refactor.widgets.non_clickable_collapsible.pyperclip.copy"
    ) as mock_copy:
        async with app.run_test() as _pilot:
            app.notify = MagicMock()

            event = NonClickableCollapsibleTitle.CopyRequested()
            collapsible._on_non_clickable_collapsible_title_copy_requested(event)

            # No clipboard interaction when empty
            mock_copy.assert_not_called()

            # Warning notification is shown
            app.notify.assert_called_once()
            args, kwargs = app.notify.call_args
            assert "No content to copy" in args[0]
            assert kwargs.get("title") == "Copy Warning"
            assert kwargs.get("severity") == "warning"
