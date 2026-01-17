"""Cloud setup indicator widget with animated spinner."""

from textual.timer import Timer
from textual.widgets import Static

from openhands_cli.theme import OPENHANDS_THEME


class CloudSetupIndicator(Static):
    """Indicator showing cloud conversation setup progress with animated spinner."""

    DEFAULT_CSS = """
    CloudSetupIndicator {
        height: 1;
        padding: 0 1;
    }
    """

    # Braille pattern spinner - smooth and professional
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"]

    def __init__(self, **kwargs) -> None:
        super().__init__("", id="cloud_setup_indicator", **kwargs)
        self._timer: Timer | None = None
        self._frame: int = 0

    def on_mount(self) -> None:
        """Start the spinner animation on mount."""
        self._update_text()
        self._timer = self.set_interval(0.1, self._on_tick)

    def on_unmount(self) -> None:
        """Stop the spinner animation on unmount."""
        if self._timer:
            self._timer.stop()
            self._timer = None

    def _on_tick(self) -> None:
        """Update spinner frame."""
        self._frame = (self._frame + 1) % len(self.SPINNER_FRAMES)
        self._update_text()

    def _update_text(self) -> None:
        """Update the indicator text with current spinner frame."""
        spinner = self.SPINNER_FRAMES[self._frame]
        self.update(
            f"[{OPENHANDS_THEME.warning}]☁️  Setting up cloud conversation... "
            f"Please wait {spinner}[/{OPENHANDS_THEME.warning}]"
        )
