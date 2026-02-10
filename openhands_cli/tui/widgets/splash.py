"""Splash content widget for the OpenHands CLI TUI.

SplashContent encapsulates all splash screen widgets and manages their
lifecycle through reactive binding:

1. **Reactive binding** (`data_bind`): conversation_id and loaded_resources
   are bound from ConversationContainer for automatic updates.

2. **Direct initialization** (`initialize()`): Called by OpenHandsApp during
   UI setup to populate and show the splash content.

Example:
    # In ConversationContainer.compose():
    yield SplashContent(id="splash_content").data_bind(
        conversation_id=ConversationContainer.conversation_id,
        loaded_resources=ConversationContainer.loaded_resources,
    )

    # In OpenHandsApp._initialize_main_ui():
    splash_content = self.query_one("#splash_content", SplashContent)
    splash_content.initialize(has_critic=True)
    # Resources are set via: conversation_state.set_loaded_resources(resources)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container
from textual.reactive import var
from textual.widgets import Static

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.splash import get_conversation_text, get_splash_content


if TYPE_CHECKING:
    from openhands_cli.tui.content.resources import LoadedResourcesInfo


class SplashContent(Container):
    """Container for all splash screen content.

    This widget encapsulates all splash-related widgets as Static children:
    - Banner (ASCII art)
    - Version info
    - Status panel
    - Conversation ID (auto-updates when conversation_id changes)
    - Instructions header and text
    - Update notice (conditional)
    - Critic notice (conditional)
    - Loaded resources collapsible (reactive, shown when resources are set)

    Lifecycle:
    - On mount: Content is hidden (waiting for initialization)
    - On initialize(): Content is populated and shown
    - On conversation_id change: Conversation text updates reactively
    - On loaded_resources change: Resources collapsible is added/updated

    Uses data_bind() for conversation_id and loaded_resources to enable
    reactive updates from ConversationContainer.
    """

    # Reactive property bound from ConversationContainer for conversation switching
    # None indicates switching in progress
    conversation_id: var[uuid.UUID | None] = var(None)

    # Reactive property bound from ConversationContainer for loaded resources
    # None indicates resources not yet loaded
    loaded_resources: var[LoadedResourcesInfo | None] = var(None)

    # Internal state (not in ConversationContainer - widget owns its initialization)
    _is_initialized: bool = False
    _has_critic: bool = False

    def __init__(self, **kwargs) -> None:
        """Initialize the splash content container."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Create splash content child widgets.

        All children are Static widgets that start hidden.
        Content is populated when initialize() is called.
        """
        yield Static(id="splash_banner", classes="splash-banner")
        yield Static(id="splash_version", classes="splash-version")
        yield Static(id="splash_status", classes="status-panel")
        yield Static(id="splash_conversation", classes="conversation-panel")
        yield Static(
            id="splash_instructions_header", classes="splash-instruction-header"
        )
        yield Static(id="splash_instructions", classes="splash-instruction")
        yield Static(id="splash_update_notice", classes="splash-update-notice")
        yield Static(id="splash_critic_notice", classes="splash-critic-notice")

    def initialize(self, *, has_critic: bool = False) -> None:
        """Initialize and show the splash content.

        Called by OpenHandsApp during UI setup. This is a one-time
        operation that populates all splash widgets and makes them visible.

        Note: Loaded resources are handled reactively via data_bind to
        loaded_resources. When ConversationContainer.loaded_resources is set,
        watch_loaded_resources will automatically add the collapsible.

        Args:
            has_critic: Whether the agent has a critic configured.
        """
        if self._is_initialized:
            return

        self._has_critic = has_critic
        self._populate_content()
        self._is_initialized = True

    def watch_loaded_resources(
        self,
        _old_value: LoadedResourcesInfo | None,
        new_value: LoadedResourcesInfo | None,
    ) -> None:
        """Handle loaded_resources changes reactively.

        When resources are set on ConversationContainer, this watcher
        automatically adds or updates the loaded resources collapsible.
        """
        if not self._is_initialized:
            return

        if new_value and new_value.has_resources():
            self._add_or_update_loaded_resources_collapsible(new_value)

    def _add_or_update_loaded_resources_collapsible(
        self, loaded_resources: LoadedResourcesInfo
    ) -> None:
        """Add or update the collapsible showing skills, hooks, and MCPs."""
        from openhands_cli.tui.widgets.collapsible import Collapsible

        summary = loaded_resources.get_summary()
        details = loaded_resources.get_details()

        # Check if collapsible already exists
        existing = self.query("#loaded_resources_collapsible")
        if existing:
            # Update existing collapsible
            collapsible = existing.first(Collapsible)
            collapsible.update_title(f"Loaded: {summary}")
            collapsible.update_content(details)
        else:
            # Create new collapsible
            collapsible = Collapsible(
                details,
                title=f"Loaded: {summary}",
                collapsed=True,
                id="loaded_resources_collapsible",
                border_color=OPENHANDS_THEME.accent,
            )
            self.mount(collapsible)

    @property
    def is_initialized(self) -> bool:
        """Check if splash content has been initialized."""
        return self._is_initialized

    def watch_conversation_id(
        self, _old_value: uuid.UUID | None, _new_value: uuid.UUID | None
    ) -> None:
        """Update conversation display when conversation_id changes.

        This enables reactive updates when switching conversations
        via the history panel or /new command. Skips update when
        conversation_id is None (during switching).
        """
        if self._is_initialized and self.conversation_id is not None:
            conversation_text = get_conversation_text(
                self.conversation_id.hex, theme=OPENHANDS_THEME
            )
            self.query_one("#splash_conversation", Static).update(conversation_text)

    def _populate_content(self) -> None:
        """Populate splash content widgets with actual content."""
        # Use empty string if conversation_id is None (shouldn't happen during init)
        conv_id_hex = self.conversation_id.hex if self.conversation_id else ""
        splash_content = get_splash_content(
            conversation_id=conv_id_hex,
            theme=OPENHANDS_THEME,
            has_critic=self._has_critic,
        )

        # Update individual splash widgets
        self.query_one("#splash_banner", Static).update(splash_content["banner"])
        self.query_one("#splash_version", Static).update(splash_content["version"])
        self.query_one("#splash_status", Static).update(splash_content["status_text"])
        self.query_one("#splash_conversation", Static).update(
            splash_content["conversation_text"]
        )
        self.query_one("#splash_instructions_header", Static).update(
            splash_content["instructions_header"]
        )

        # Join instructions into a single string
        instructions_text = "\n".join(splash_content["instructions"])
        self.query_one("#splash_instructions", Static).update(instructions_text)

        # Update notice (show only if content exists)
        update_notice_widget = self.query_one("#splash_update_notice", Static)
        if splash_content["update_notice"]:
            update_notice_widget.update(splash_content["update_notice"])
            update_notice_widget.display = True
        else:
            update_notice_widget.display = False

        # Update critic notice (show only if content exists)
        critic_notice_widget = self.query_one("#splash_critic_notice", Static)
        if splash_content["critic_notice"]:
            critic_notice_widget.update(splash_content["critic_notice"])
            critic_notice_widget.display = True
        else:
            critic_notice_widget.display = False
