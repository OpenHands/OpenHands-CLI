"""Right side panel container for agent plan and ask agent functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from openhands_cli.tui.panels.ask_agent_panel import AskAgentPanel
from openhands_cli.tui.panels.plan_side_panel import PlanSidePanel
from openhands_cli.tui.panels.right_side_panel_style import RIGHT_SIDE_PANEL_STYLE


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp


class RightSidePanel(Vertical):
    """Container panel that holds both the Agent Plan and Ask Agent panels.

    This panel appears on the right side of the screen and contains:
    - Agent Plan panel at the top (showing task progress)
    - A divider
    - Ask Agent panel at the bottom (for asking questions about the conversation)
    """

    DEFAULT_CSS = RIGHT_SIDE_PANEL_STYLE

    def __init__(self, app: OpenHandsApp, **kwargs):
        """Initialize the Right Side Panel."""
        super().__init__(**kwargs)
        self._oh_app = app
        self.user_dismissed = False
        self._plan_panel: PlanSidePanel | None = None
        self._ask_agent_panel: AskAgentPanel | None = None

    @property
    def plan_panel(self) -> PlanSidePanel | None:
        """Get the plan panel instance."""
        return self._plan_panel

    def compose(self):
        """Compose the Right Side Panel content."""
        # Header row with close button
        with Horizontal(classes="right-panel-header-row"):
            yield Static("Agent Panel", classes="right-panel-header")
            yield Button("✕", id="right-panel-close-btn")

        # Plan panel (agent tasks)
        self._plan_panel = PlanSidePanel(self._oh_app)
        yield self._plan_panel

        # Divider between panels
        yield Static("", classes="right-panel-divider")

        # Ask agent panel
        self._ask_agent_panel = AskAgentPanel(self._oh_app)
        yield self._ask_agent_panel

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "right-panel-close-btn":
            self.toggle()

    def toggle(self) -> None:
        """Toggle the Right Side Panel on/off."""
        if self.is_on_screen:
            self.remove()
            self.user_dismissed = True
        else:
            content_area = self._oh_app.query_one("#content_area", Horizontal)
            content_area.mount(self)
            self.refresh_from_disk()

    def refresh_from_disk(self) -> None:
        """Refresh the plan panel from disk."""
        if self._plan_panel:
            self._plan_panel.refresh_from_disk()
