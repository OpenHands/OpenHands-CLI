from textual import on
from textual.content import Content
from textual.events import Paste
from textual.message import Message
from textual.widgets import TextArea


class AutoGrowTextArea(TextArea):
    """A TextArea that auto-grows with content and supports soft wrapping.

    This implementation is based on the toad project's approach:
    - Uses soft_wrap=True for automatic line wrapping at word boundaries
    - Uses compact=True to remove default borders
    - CSS height: auto makes it grow based on content
    - CSS max-height limits maximum growth
    """

    class PasteDetected(Message):
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
        # Cache for cursor position calculation
        self._cached_line_offsets: list[int] | None = None
        self._cached_text_for_offsets: str | None = None

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
            self.post_message(self.PasteDetected(event.text))
            event.prevent_default()
            event.stop()
        # For single-line content, let the default paste behavior handle it

    def _get_line_offsets(self) -> list[int]:
        """Get cached line start offsets for efficient cursor position calculation.

        Returns a list where index i contains the character offset where line i starts.
        This is cached and invalidated when text changes.
        """
        current_text = self.text
        if (
            self._cached_line_offsets is not None
            and self._cached_text_for_offsets == current_text
        ):
            return self._cached_line_offsets

        # Compute line offsets: offset[i] = character position where line i starts
        offsets = [0]
        pos = 0
        for char in current_text:
            pos += 1
            if char == "\n":
                offsets.append(pos)

        self._cached_line_offsets = offsets
        self._cached_text_for_offsets = current_text
        return offsets

