"""Abstract input mode protocol for InputField."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from textual.widget import Widget


if TYPE_CHECKING:
    from openhands_cli.tui.widgets.user_input.autocomplete_coordinator import (
        AutocompleteCoordinator,
    )


class InputMode(ABC):
    """Abstract base class for input modes.

    Each mode encapsulates the behavior of a specific input style
    (single-line vs multiline), including:
    - Widget management
    - Event handling (enter, paste, key navigation)
    - Text getting/setting
    """

    @property
    @abstractmethod
    def widget(self) -> Widget:
        """Get the underlying widget for this mode."""
        ...

    @property
    @abstractmethod
    def text(self) -> str:
        """Get the current text content."""
        ...

    @text.setter
    @abstractmethod
    def text(self, value: str) -> None:
        """Set the text content."""
        ...

    @abstractmethod
    def focus(self) -> None:
        """Focus this mode's widget."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear the text content."""
        ...

    @abstractmethod
    def move_cursor_to_end(self) -> None:
        """Move cursor to the end of the text."""
        ...

    @abstractmethod
    def show(self) -> None:
        """Make this mode's widget visible."""
        ...

    @abstractmethod
    def hide(self) -> None:
        """Hide this mode's widget."""
        ...

    def get_autocomplete_coordinator(self) -> "AutocompleteCoordinator | None":
        """Get the autocomplete coordinator if this mode supports it.

        Returns None by default. Override in modes that support autocomplete.
        """
        return None

    def on_activate(self) -> None:
        """Called when this mode becomes active. Override for custom behavior."""
        self.show()
        self.focus()

    def on_deactivate(self) -> None:
        """Called when this mode is deactivated. Override for custom behavior."""
        self.hide()
