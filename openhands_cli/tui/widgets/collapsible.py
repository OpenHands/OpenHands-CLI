"""Collapsible widget for OpenHands CLI.

This module provides a Collapsible widget that can be toggled by clicking on the
title or pressing Enter when focused. It also supports programmatic control via
Ctrl+O to toggle all cells at once.
"""

from typing import TYPE_CHECKING, Any, ClassVar, Protocol

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.content import Content, ContentText
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


if TYPE_CHECKING:
    from textual.dom import DOMNode


class CollapsibleTitle(Container, can_focus=True):
    """Title and symbol for the Collapsible widget.

    Supports click-to-toggle and keyboard navigation (Enter to toggle).
    Emits Navigate messages for arrow key navigation, which should be
    handled by the parent App that owns the list of collapsibles.
    """

    ALLOW_SELECT = False
    DEFAULT_CSS = """
    CollapsibleTitle {
        width: 100%;
        height: auto;
        padding: 0 1;
        text-style: $block-cursor-blurred-text-style;
        color: $block-cursor-blurred-foreground;

        &:hover {
            background: $block-hover-background;
            color: $foreground;
        }

        &:focus {
            text-style: $block-cursor-text-style;
            background: $block-cursor-background;
            color: $block-cursor-foreground;
        }
    }

    CollapsibleTitle .title-text {
        width: 1fr;
        height: auto;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "toggle_collapsible", "Toggle collapsible", show=False),
        Binding("up", "navigate_previous", "Previous cell", show=False),
        Binding("down", "navigate_next", "Next cell", show=False),
    ]

    collapsed = reactive(True)
    label: reactive[ContentText] = reactive(Content("Toggle"))

    def __init__(
        self,
        *,
        label: ContentText,
        collapsed_symbol: str,
        expanded_symbol: str,
        collapsed: bool,
    ) -> None:
        # Initialize _title_static first to avoid AttributeError in watchers
        self._title_static: Static | None = None
        super().__init__()
        self.collapsed_symbol = collapsed_symbol
        self.expanded_symbol = expanded_symbol

        # Set reactive properties after _title_static is initialized
        self.label = Content.from_text(label)
        self.collapsed = collapsed

    class Toggle(Message):
        """Request to toggle the collapsible state."""

    class Navigate(Message):
        """Request to navigate to a sibling cell.

        This message bubbles up to the App, which owns the list of collapsibles
        and can efficiently handle navigation using direct index lookup.

        The message includes the source collapsible reference, eliminating the
        need for the App to search through all collapsibles to find which one
        is currently focused.
        """

        def __init__(self, direction: int, collapsible: "Collapsible") -> None:
            """Initialize Navigate message.

            Args:
                direction: -1 for previous (up), 1 for next (down)
                collapsible: The source Collapsible widget requesting navigation
            """
            super().__init__()
            self.direction = direction
            self.collapsible = collapsible

    async def _on_click(self, event: events.Click) -> None:
        """Toggle collapsible when title area is clicked."""
        event.stop()
        self.post_message(self.Toggle())

    def action_toggle_collapsible(self) -> None:
        """Toggle the collapsible when Enter is pressed."""
        self.post_message(self.Toggle())

    def _find_parent_collapsible(self) -> "Collapsible | None":
        """Find the parent Collapsible widget by walking up the DOM tree."""
        node = self.parent
        while node is not None:
            if isinstance(node, Collapsible):
                return node
            node = node.parent
        return None

    def action_navigate_previous(self) -> None:
        """Request navigation to previous cell (up arrow)."""
        parent = self._find_parent_collapsible()
        if parent is not None:
            self.post_message(self.Navigate(direction=-1, collapsible=parent))

    def action_navigate_next(self) -> None:
        """Request navigation to next cell (down arrow)."""
        parent = self._find_parent_collapsible()
        if parent is not None:
            self.post_message(self.Navigate(direction=1, collapsible=parent))

    def compose(self) -> ComposeResult:
        """Compose the title."""
        self._title_static = Static(classes="title-text")
        yield self._title_static

    def on_mount(self) -> None:
        """Initialize the title display."""
        self._update_label()

    def _update_label(self) -> None:
        """Update the title text display."""
        if self._title_static is None:
            return

        assert isinstance(self.label, Content)
        if self.collapsed:
            content = Content.assemble(self.collapsed_symbol, " ", self.label)
        else:
            content = Content.assemble(self.expanded_symbol, " ", self.label)

        self._title_static.update(content)

    def _watch_collapsed(self, _collapsed: bool) -> None:
        self._update_label()


class CollapsibleContents(Container):
    DEFAULT_CSS = """
    CollapsibleContents {
        width: 100%;
        height: auto;
        padding: 1 0 0 3;
    }
    """


class Collapsible(Widget):
    """A collapsible container with click and keyboard toggle support.

    Can be toggled by:
    - Clicking the title bar
    - Pressing Enter when the title is focused
    - Arrow keys to navigate between cells (handled by parent App)
    - Ctrl+O to toggle all cells at once (handled by parent App)
    """

    ALLOW_MAXIMIZE = True
    collapsed = reactive(True, init=False)
    title = reactive("Toggle")

    DEFAULT_CSS = """
    Collapsible {
        width: 1fr;
        height: auto;
        background: $background;
        padding-bottom: 1;
        padding-left: 1;

        &:focus-within {
            background-tint: $foreground 3%;
        }

        &.-collapsed > CollapsibleContents {
            display: none;
        }
    }
    """

    def __init__(
        self,
        content: Any,
        *,
        title: str | Text = "Toggle",
        collapsed: bool = True,
        collapsed_symbol: str = "▶",
        expanded_symbol: str = "▼",
        border_color: str | None = "$secondary",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialize a Collapsible widget.

        Args:
            content: Content that will be collapsed/expanded (converted to string).
            title: Title of the collapsed/expanded contents (str or Rich Text).
            collapsed: Default status of the contents.
            collapsed_symbol: Collapsed symbol before the title.
            expanded_symbol: Expanded symbol before the title.
            border_color: CSS color for the left border. None to disable border.
            name: The name of the collapsible.
            id: The ID of the collapsible in the DOM.
            classes: The CSS classes of the collapsible.
            disabled: Whether the collapsible is disabled or not.
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._title = CollapsibleTitle(
            label=title,
            collapsed_symbol=collapsed_symbol,
            expanded_symbol=expanded_symbol,
            collapsed=collapsed,
        )
        self.title = title
        # Pass the original content to Static with markup=False to prevent
        # MarkupError when content contains special characters like quotes,
        # brackets, etc. This follows the same approach as toad's tool_call.py.
        self._content_widget = Static(content, markup=False)
        self.collapsed = collapsed
        self._watch_collapsed(collapsed)
        if border_color is not None:
            # Use "tall" for a thin vertical line, with gray color
            self.styles.border_left = ("tall", "gray")

    def update_title(self, new_title: str | Text) -> None:
        """Update the title of the collapsible.

        Args:
            new_title: The new title text to display (str or Rich Text).
        """
        self.title = new_title
        self._title.label = Content.from_text(new_title)
        self._title._update_label()

    def update_content(self, new_content: Any) -> None:
        """Update the content of the collapsible.

        Args:
            new_content: The new content to display (can be string or Rich renderable).
        """
        self._content_string = str(new_content)
        self._content_widget.update(new_content)

    def _on_collapsible_title_toggle(self, event: CollapsibleTitle.Toggle) -> None:
        """Handle toggle request from title click or keyboard."""
        event.stop()
        self.collapsed = not self.collapsed

    def _watch_collapsed(self, collapsed: bool) -> None:
        """Update collapsed state when reactive is changed."""
        self._title.collapsed = collapsed
        self.set_class(collapsed, "-collapsed")
        if self.is_mounted:
            self.call_after_refresh(self.scroll_visible)

    def compose(self) -> ComposeResult:
        yield self._title
        with CollapsibleContents():
            yield self._content_widget


class _HasQueryOne(Protocol):
    """Protocol for classes that support query_one method (e.g., Textual App)."""

    def query_one(self, selector: str) -> "DOMNode": ...


class CollapsibleNavigationMixin:
    """Mixin providing navigation handler for apps with Collapsible widgets.

    Apps that contain Collapsible widgets can use this mixin to handle
    arrow key navigation between cells. The app must have a container
    with id="main_display" containing the Collapsible widgets.

    Usage:
        class MyApp(CollapsibleNavigationMixin, App):
            ...
    """

    def on_collapsible_title_navigate(
        self: _HasQueryOne, event: CollapsibleTitle.Navigate
    ) -> None:
        """Handle navigation between collapsible cells.

        The Navigate message includes the source collapsible, so we can
        directly find its index without searching through all cells.
        """
        event.stop()

        # Get all collapsibles as a list for index-based navigation
        main_display = self.query_one("#main_display")
        collapsibles = list(main_display.query(Collapsible))
        if not collapsibles:
            return

        # Use the collapsible reference from the event directly
        try:
            current_index = collapsibles.index(event.collapsible)
        except ValueError:
            # Collapsible not in list (this shouldn't happen)
            return

        # Calculate target index
        target_index = current_index + event.direction

        # Check bounds
        if target_index < 0 or target_index >= len(collapsibles):
            return

        # Focus the target collapsible's title
        target = collapsibles[target_index]
        target_title = target.query_one(CollapsibleTitle)
        target_title.focus()
        target.scroll_visible()
