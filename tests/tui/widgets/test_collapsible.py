import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

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

        with VerticalScroll(id="scroll_view"):
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
