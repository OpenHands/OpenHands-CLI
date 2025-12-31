"""Custom non-clickable Collapsible widget for OpenHands CLI.

This module provides a Collapsible widget that cannot be toggled by clicking,
only through programmatic control (like Ctrl+E). It also has a dimmer gray background.
"""

import platform
from typing import Any, ClassVar

import pyperclip
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal
from textual.content import Content, ContentText
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Static


def _is_linux() -> bool:
    """Check if the current platform is Linux."""
    return platform.system() == "Linux"


class NonClickableCollapsibleTitle(Container, can_focus=False):
    """Title and symbol for the NonClickableCollapsible that ignores click events."""

    ALLOW_SELECT = False
    DEFAULT_CSS = """
    NonClickableCollapsibleTitle {
        width: 100%;
        height: auto;
        padding: 0 1;
        text-style: $block-cursor-blurred-text-style;
        color: $block-cursor-blurred-foreground;
    }

    NonClickableCollapsibleTitle Horizontal {
        width: 100%;
        height: auto;
    }

    NonClickableCollapsibleTitle .title-text {
        width: 1fr;
        height: auto;
    }

    NonClickableCollapsibleTitle .copy-button {
        width: auto;
        height: 1;
        min-width: 4;
        margin-left: 1;
        background: transparent;
        border: none;
        color: $text-muted;
        text-style: none;
    }

    NonClickableCollapsibleTitle .copy-button:hover {
        background: $surface-lighten-1;
        color: $text;
        text-style: bold;
    }

    NonClickableCollapsibleTitle .copy-button:focus {
        background: $surface-lighten-2;
        color: $text;
        text-style: bold;
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
        # Initialize _title_static first to avoid AttributeError in watchers
        self._title_static: Static | None = None
        super().__init__()
        self.collapsed_symbol = collapsed_symbol
        self.expanded_symbol = expanded_symbol

        # Set reactive properties after _title_static is initialized
        self.label = Content.from_text(label)
        self.collapsed = collapsed

    class CopyRequested(Message):
        """Request to copy content."""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press - post CopyRequested when copy button is clicked."""
        if event.button.id == "copy-btn":
            event.stop()
            self.post_message(self.CopyRequested())

    def compose(self) -> ComposeResult:
        """Compose the title with copy button."""
        self._title_static = Static(classes="title-text")
        with Horizontal():
            yield self._title_static
            yield Button("📋", id="copy-btn", classes="copy-button")

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


class NonClickableCollapsibleContents(Container):
    DEFAULT_CSS = """
    NonClickableCollapsibleContents {
        width: 100%;
        height: auto;
        padding: 1 0 0 3;
    }
    """


class NonClickableCollapsible(Widget):
    """A collapsible container that cannot be toggled by clicking."""

    ALLOW_MAXIMIZE = True
    collapsed = reactive(True, init=False)
    title = reactive("Toggle")

    DEFAULT_CSS = """
    NonClickableCollapsible {
        width: 1fr;
        height: auto;
        background: $background;
        padding-bottom: 1;
        padding-left: 1;

        &:focus-within {
            background-tint: $foreground 3%;
        }

        &.-collapsed > NonClickableCollapsibleContents {
            display: none;
        }
    }
    """

    def __init__(
        self,
        content: Any,
        *,
        title: str = "Toggle",
        collapsed: bool = True,
        collapsed_symbol: str = "▶",
        expanded_symbol: str = "▼",
        border_color: str = "$secondary",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialize a NonClickableCollapsible widget.

        Args:
            content: Content that will be collapsed/expanded (converted to string).
            title: Title of the collapsed/expanded contents.
            collapsed: Default status of the contents.
            collapsed_symbol: Collapsed symbol before the title.
            expanded_symbol: Expanded symbol before the title.
            border_color: CSS color for the left border.
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
        self._content_string = str(content)  # String version for copying
        # Pass the original content to Static (can be Rich renderable)
        self._content_widget = Static(content)
        self.collapsed = collapsed
        self._watch_collapsed(collapsed)
        self.styles.border_left = ("thick", border_color)

    def _on_non_clickable_collapsible_title_copy_requested(
        self, event: NonClickableCollapsibleTitle.CopyRequested
    ) -> None:
        """Handle copy request from the title.

        Uses a two-layer approach for clipboard access:
        1. Primary: pyperclip for direct OS clipboard access
        2. Fallback: Textual's copy_to_clipboard (OSC 52 escape sequence)

        This ensures clipboard works across different terminal environments.
        """
        event.stop()

        if not self._content_string:
            self.app.notify(
                "No content to copy",
                title="Copy Warning",
                severity="warning",
                timeout=2,
            )
            return

        pyperclip_success = False
        # Primary: Try pyperclip for direct OS clipboard access
        try:
            pyperclip.copy(self._content_string)
            pyperclip_success = True
        except pyperclip.PyperclipException:
            # pyperclip failed - will try OSC 52 fallback
            pass

        # Also try OSC 52 - this doesn't raise errors, it just sends escape
        # sequences. We do both because pyperclip and OSC 52 can target
        # different clipboards (e.g., remote terminals, tmux, SSH sessions)
        self.app.copy_to_clipboard(self._content_string)

        if pyperclip_success:
            self.app.notify(
                "Content copied to clipboard!", title="Copy Success", timeout=2
            )
        elif _is_linux():
            # On Linux without pyperclip working, OSC 52 may or may not work
            self.app.notify(
                "Copy attempted. If it didn't work, try: sudo apt install xclip",
                title="Copy",
                timeout=4,
            )
        else:
            self.app.notify(
                "Content copied to clipboard!", title="Copy Success", timeout=2
            )

    def _watch_collapsed(self, collapsed: bool) -> None:
        """Update collapsed state when reactive is changed."""
        self._title.collapsed = collapsed
        self.set_class(collapsed, "-collapsed")
        if self.is_mounted:
            self.call_after_refresh(self.scroll_visible)

    def compose(self) -> ComposeResult:
        yield self._title
        with NonClickableCollapsibleContents():
            yield self._content_widget
