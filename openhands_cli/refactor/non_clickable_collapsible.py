"""Custom non-clickable Collapsible widget for OpenHands CLI.

This module provides a Collapsible widget that cannot be toggled by clicking,
only through programmatic control (like Ctrl+E). It also has a dimmer gray background.
"""

from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.content import Content, ContentText
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class NonClickableCollapsibleTitle(Static, can_focus=False):
    """Title and symbol for the NonClickableCollapsible that ignores click events."""

    ALLOW_SELECT = False
    DEFAULT_CSS = """
    NonClickableCollapsibleTitle {
        width: auto;
        height: auto;
        padding: 0 1;
        text-style: $block-cursor-blurred-text-style;
        color: $block-cursor-blurred-foreground;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "toggle_collapsible", "Toggle collapsible", show=False)
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
        super().__init__()
        self.collapsed_symbol = collapsed_symbol
        self.expanded_symbol = expanded_symbol
        self.label = Content.from_text(label)
        self.collapsed = collapsed

    class Toggle(Message):
        """Request toggle."""

    async def _on_click(self, event: events.Click) -> None:
        """Override click handler to do nothing - disable click interaction."""
        event.stop()
        event.prevent_default()
        # Do nothing - this disables click-to-toggle functionality

    async def _on_mouse_down(self, event: events.MouseDown) -> None:
        """Override mouse down to prevent focus and interaction."""
        event.stop()
        event.prevent_default()

    async def _on_mouse_up(self, event: events.MouseUp) -> None:
        """Override mouse up to prevent focus and interaction."""
        event.stop()
        event.prevent_default()

    def action_toggle_collapsible(self) -> None:
        """Toggle the state of the parent collapsible."""
        self.post_message(self.Toggle())

    def validate_label(self, label: ContentText) -> Content:
        return Content.from_text(label)

    def _update_label(self) -> None:
        assert isinstance(self.label, Content)
        if self.collapsed:
            self.update(Content.assemble(self.collapsed_symbol, " ", self.label))
        else:
            self.update(Content.assemble(self.expanded_symbol, " ", self.label))

    def _watch_label(self) -> None:
        self._update_label()

    def _watch_collapsed(self, _collapsed: bool) -> None:
        self._update_label()


class NonClickableCollapsible(Widget):
    """A collapsible container that cannot be toggled by clicking."""

    ALLOW_MAXIMIZE = True
    collapsed = reactive(True, init=False)
    title = reactive("Toggle")

    DEFAULT_CSS = """
    NonClickableCollapsible {
        width: 1fr;
        height: auto;
        background: $surface-darken-1;
        border-top: hkey $background;
        padding-bottom: 1;
        padding-left: 1;

        &:focus-within {
            background-tint: $foreground 3%;
        }

        &.-collapsed > Contents {
            display: none;
        }
    }
    """

    class Toggled(Message):
        """Parent class subclassed by `NonClickableCollapsible` messages."""

        def __init__(self, collapsible: "NonClickableCollapsible") -> None:
            self.collapsible: NonClickableCollapsible = collapsible
            super().__init__()

        @property
        def control(self) -> "NonClickableCollapsible":
            """An alias for the collapsible."""
            return self.collapsible

    class Expanded(Toggled):
        """Event sent when the `NonClickableCollapsible` widget is expanded."""

    class Collapsed(Toggled):
        """Event sent when the `NonClickableCollapsible` widget is collapsed."""

    class Contents(Container):
        DEFAULT_CSS = """
        Contents {
            width: 100%;
            height: auto;
            padding: 1 0 0 3;
        }
        """

    def __init__(
        self,
        *children: Widget,
        title: str = "Toggle",
        collapsed: bool = True,
        collapsed_symbol: str = "▶",
        expanded_symbol: str = "▼",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialize a NonClickableCollapsible widget.

        Args:
            *children: Contents that will be collapsed/expanded.
            title: Title of the collapsed/expanded contents.
            collapsed: Default status of the contents.
            collapsed_symbol: Collapsed symbol before the title.
            expanded_symbol: Expanded symbol before the title.
            name: The name of the collapsible.
            id: The ID of the collapsible in the DOM.
            classes: The CSS classes of the collapsible.
            disabled: Whether the collapsible is disabled or not.
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._title = NonClickableCollapsibleTitle(
            label=title,
            collapsed_symbol=collapsed_symbol,
            expanded_symbol=expanded_symbol,
            collapsed=collapsed,
        )
        self.title = title
        self._contents_list: list[Widget] = list(children)
        self.collapsed = collapsed

    def _on_non_clickable_collapsible_title_toggle(
        self, event: NonClickableCollapsibleTitle.Toggle
    ) -> None:
        event.stop()
        self.collapsed = not self.collapsed

    def _watch_collapsed(self, collapsed: bool) -> None:
        """Update collapsed state when reactive is changed."""
        self._update_collapsed(collapsed)
        if self.collapsed:
            self.post_message(self.Collapsed(self))
        else:
            self.post_message(self.Expanded(self))
        if self.is_mounted:
            self.call_after_refresh(self.scroll_visible)

    def _update_collapsed(self, collapsed: bool) -> None:
        """Update children to match collapsed state."""
        try:
            self._title.collapsed = collapsed
            self.set_class(collapsed, "-collapsed")
        except NoMatches:
            pass

    def _on_mount(self, event: events.Mount) -> None:  # noqa: ARG002
        """Initialise collapsed state."""
        self._update_collapsed(self.collapsed)

    def compose(self) -> ComposeResult:
        yield self._title
        with self.Contents():
            yield from self._contents_list

    def compose_add_child(self, widget: Widget) -> None:
        """When using the context manager compose syntax, we want to attach nodes.

        Args:
            widget: A Widget to add.
        """
        self._contents_list.append(widget)

    def _watch_title(self, title: str) -> None:
        self._title.label = title
