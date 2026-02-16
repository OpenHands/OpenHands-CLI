from typing import ClassVar

from textual import on
from textual.binding import Binding
from textual.content import Content
from textual.events import Paste
from textual.message import Message
from textual.widgets import TextArea


class SingleLineInputWithWrapping(TextArea):
    """A TextArea that auto-grows with content and supports soft wrapping.

    This implementation is based on the toad project's approach:
    - Uses soft_wrap=True for automatic line wrapping at word boundaries
    - Uses compact=True to remove default borders
    - CSS height: auto makes it grow based on content
    - CSS max-height limits maximum growth
    """

    BINDINGS: ClassVar = [
        # Override default ctrl+a (cursor_line_start) to select all instead
        Binding("ctrl+a", "select_all", "Select all", show=True),
    ]

    class MultiLinePasteDetected(Message):
        """Message sent when multi-line paste is detected."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class EnterPressed(Message):
        """Message sent when Enter is pressed (for submission)."""

    def __init__(
        self,
        text: str = "",
        *,
        placeholder: str | Content = "",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            text,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
            soft_wrap=True,  # Enable soft wrapping at word boundaries
            show_line_numbers=False,
            highlight_cursor_line=False,
        )
        self.compact = True
        self._placeholder = placeholder

    def on_mount(self) -> None:
        """Configure the text area on mount."""
        # Set placeholder after mount
        if self._placeholder:
            self.placeholder = (
                Content(self._placeholder)
                if isinstance(self._placeholder, str)
                else self._placeholder
            )

    async def _on_key(self, event) -> None:
        """Intercept Enter key before TextArea processes it."""
        if event.key == "enter":
            # Post message to parent and prevent default newline insertion
            self.post_message(self.EnterPressed())
            event.prevent_default()
            event.stop()
            return
        # Let parent class handle other keys
        await super()._on_key(event)

    @on(Paste)
    async def _on_paste(self, event: Paste) -> None:
        """Handle paste events and detect multi-line content."""
        if "\n" in event.text or "\r" in event.text:
            # Multi-line content detected - notify parent
            self.post_message(self.MultiLinePasteDetected(event.text))
            event.prevent_default()
            event.stop()
        # For single-line content, let the default paste behavior handle it
