"""Input area container for status lines and input field.

This container is docked to the bottom of ConversationView (as a sibling of
ScrollableContent) and handles:
- SlashCommandSubmitted: Executes slash commands
- Clearing scroll_view content when conversation_id changes

Widget Hierarchy:
    ConversationView(#conversation_view)
    ├── ScrollableContent(#scroll_view)  ← sibling, content rendered here
    └── InputAreaContainer(#input_area)  ← docked to bottom
        ├── WorkingStatusLine
        ├── InputField  ← posts messages
        └── InfoStatusLine

Note: UserInputSubmitted bubbles up to ConversationView for rendering and processing.
The child widgets are composed by ConversationView (not this container) to enable
data_bind() to work properly.
"""

import asyncio
import uuid
from typing import TYPE_CHECKING

from textual import on
from textual.containers import Container
from textual.reactive import var

from openhands_cli.tui.core.commands import show_help
from openhands_cli.tui.messages import (
    NewConversationRequested,
    SlashCommandSubmitted,
)


if TYPE_CHECKING:
    from openhands_cli.tui.widgets.main_display import ScrollableContent


class InputAreaContainer(Container):
    """Container for the input area that handles slash commands.

    InputAreaContainer is responsible for:
    - Executing slash commands (SlashCommandSubmitted)
    - Clearing scroll_view content when conversation_id changes

    Note: UserInputSubmitted bubbles up to ConversationView for rendering
    and processing.

    It delegates to self.app for:
    - Conversation runner management (owned by ConversationView)
    - Screen/modal pushing (exit, confirm, settings)
    - Side panel toggling (history)
    - Notifications

    Reactive Properties (via data_bind from ConversationView):
    - conversation_id: Current conversation ID (clears content on change)
    """

    # Reactive property bound via data_bind() to ConversationView
    conversation_id: var[uuid.UUID] = var(uuid.uuid4)

    @property
    def scroll_view(self) -> "ScrollableContent":
        """Get the sibling scrollable content area."""
        from openhands_cli.tui.widgets.main_display import ScrollableContent

        # scroll_view is a sibling - query from parent (ConversationView)
        assert self.parent is not None, "InputAreaContainer must have a parent"
        return self.parent.query_one("#scroll_view", ScrollableContent)

    def watch_conversation_id(self, old_id: uuid.UUID, new_id: uuid.UUID) -> None:
        """Clear dynamic content when conversation changes.

        When conversation_id changes, removes all dynamically added widgets
        (user messages, agent responses, etc.) while preserving:
        - SplashContent (#splash_content) - re-renders via its own binding
        """
        if old_id == new_id:
            return

        # Don't try to clear content if we're not mounted yet
        if not self.is_mounted:
            return

        try:
            scroll_view = self.scroll_view
        except Exception:
            # scroll_view might not exist yet during initialization
            return

        # Remove all children from scroll_view except splash_content
        for widget in list(scroll_view.children):
            if widget.id != "splash_content":
                widget.remove()

        # Scroll to top to show splash screen
        scroll_view.scroll_home(animate=False)

    @on(SlashCommandSubmitted)
    def _on_slash_command_submitted(self, event: SlashCommandSubmitted) -> None:
        """Handle slash commands.

        Routes to appropriate _command_* method based on the command.
        Stops event propagation since InputAreaContainer handles all commands.
        """
        event.stop()

        match event.command:
            case "help":
                self._command_help()
            case "new":
                self._command_new()
            case "history":
                self._command_history()
            case "confirm":
                self._command_confirm()
            case "condense":
                self._command_condense()
            case "feedback":
                self._command_feedback()
            case "exit":
                self._command_exit()
            case _:
                self.app.notify(
                    title="Unknown Command",
                    message=f"Unknown command: /{event.command}",
                    severity="warning",
                )

    # ---- Command Methods ----

    def _command_help(self) -> None:
        """Handle the /help command to display available commands."""
        show_help(self.scroll_view)

    def _command_new(self) -> None:
        """Handle the /new command to start a new conversation."""
        self.post_message(NewConversationRequested())

    def _command_history(self) -> None:
        """Handle the /history command to show conversation history panel."""
        from openhands_cli.tui.textual_app import OpenHandsApp

        app: OpenHandsApp = self.app  # type: ignore[assignment]
        app.action_toggle_history()

    def _command_confirm(self) -> None:
        """Handle the /confirm command to show confirmation settings modal."""
        from openhands_cli.tui.modals.confirmation_modal import (
            ConfirmationSettingsModal,
        )
        from openhands_cli.tui.textual_app import OpenHandsApp

        app: OpenHandsApp = self.app  # type: ignore[assignment]

        # Get current confirmation policy from ConversationView
        current_policy = app.conversation_view.confirmation_policy

        # Show the confirmation settings modal
        confirmation_modal = ConfirmationSettingsModal(
            current_policy=current_policy,
            on_policy_selected=app.conversation_view.set_confirmation_policy,
        )
        app.push_screen(confirmation_modal)

    def _command_condense(self) -> None:
        """Handle the /condense command to condense conversation history."""
        from openhands_cli.tui.textual_app import OpenHandsApp

        app: OpenHandsApp = self.app  # type: ignore[assignment]

        if not app.conversation_runner:
            app.notify(
                title="Condense Error",
                message="No conversation available to condense",
                severity="error",
            )
            return

        # Use the async condensation method from conversation runner
        asyncio.create_task(app.conversation_runner.condense_async())

    def _command_feedback(self) -> None:
        """Handle the /feedback command to open feedback form in browser."""
        import webbrowser

        feedback_url = "https://forms.gle/chHc5VdS3wty5DwW6"
        webbrowser.open(feedback_url)
        self.app.notify(
            title="Feedback",
            message="Opening feedback form in your browser...",
            severity="information",
        )

    def _command_exit(self) -> None:
        """Handle the /exit command with optional confirmation."""
        from openhands_cli.tui.modals.exit_modal import ExitConfirmationModal
        from openhands_cli.tui.textual_app import OpenHandsApp

        app: OpenHandsApp = self.app  # type: ignore[assignment]

        if app.exit_confirmation:
            app.push_screen(ExitConfirmationModal())
        else:
            app.exit()
