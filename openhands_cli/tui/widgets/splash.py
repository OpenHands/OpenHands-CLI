"""Splash content widget for the OpenHands CLI TUI.

SplashContent encapsulates all splash screen widgets and manages their
lifecycle through two mechanisms:

1. **Reactive binding** (`data_bind`): conversation_id is bound from ConversationView
   for automatic updates when switching conversations.

2. **Direct initialization** (`initialize()`): Called by OpenHandsApp during
   UI setup to populate and show the splash content. This separates UI
   lifecycle concerns from conversation state.

Example:
    # In ConversationView.compose():
    yield SplashContent(id="splash_content").data_bind(
        conversation_id=ConversationView.conversation_id,
    )

    # In OpenHandsApp._initialize_main_ui():
    splash_content = self.query_one("#splash_content", SplashContent)
    splash_content.initialize(has_critic=True)
"""

import uuid

from textual.app import ComposeResult
from textual.containers import Container
from textual.reactive import var
from textual.widgets import Static

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.splash import get_conversation_text, get_splash_content


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

    Lifecycle:
    - On mount: Content is hidden (waiting for initialization)
    - On initialize(): Content is populated and shown
    - On conversation_id change: Conversation text updates reactively

    Uses data_bind() for conversation_id to enable reactive updates
    when switching conversations.
    """

    # Reactive property bound from ConversationView for conversation switching
    conversation_id: var[uuid.UUID] = var(uuid.uuid4)

    # Internal state (not in ConversationView - widget owns its initialization)
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

        Args:
            has_critic: Whether the agent has a critic configured.
        """
        if self._is_initialized:
            return

        self._has_critic = has_critic
        self._populate_content()
        self._is_initialized = True

    @property
    def is_initialized(self) -> bool:
        """Check if splash content has been initialized."""
        return self._is_initialized

    def watch_conversation_id(
        self, _old_value: uuid.UUID, _new_value: uuid.UUID
    ) -> None:
        """Update conversation display when conversation_id changes.

        This enables reactive updates when switching conversations
        via the history panel or /new command.
        """
        if self._is_initialized:
            conversation_text = get_conversation_text(
                self.conversation_id.hex, theme=OPENHANDS_THEME
            )
            self.query_one("#splash_conversation", Static).update(conversation_text)

    def _populate_content(self) -> None:
        """Populate splash content widgets with actual content."""
        splash_content = get_splash_content(
            conversation_id=self.conversation_id.hex,
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
