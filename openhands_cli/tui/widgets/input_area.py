"""Input area container for status lines and input field.

This container is docked to the bottom of ConversationState (as a sibling of
ScrollableContent) and handles slash command execution.

Widget Hierarchy:
    ConversationManager (ancestor - messages bubble here)
    └── ConversationState(#conversation_state)
        ├── ScrollableContent(#scroll_view)  ← sibling, content rendered here
        └── InputAreaContainer(#input_area)  ← docked to bottom
            ├── WorkingStatusLine
            ├── InputField  ← posts messages
            └── InfoStatusLine

Message Flow:
    - SlashCommandSubmitted → InputAreaContainer posts operation messages
    - All messages bubble up to ConversationManager (ancestor)
"""

from typing import TYPE_CHECKING, cast

from textual import on
from textual.containers import Container

from openhands_cli.tui.core.commands import show_help
from openhands_cli.tui.messages import SlashCommandSubmitted


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp
    from openhands_cli.tui.widgets.main_display import ScrollableContent


class InputAreaContainer(Container):
    """Container for the input area that handles slash commands.

    InputAreaContainer posts operation messages (CreateConversation, etc.)
    that bubble up to ConversationManager, which is an ancestor in the
    widget hierarchy.

    UserInputSubmitted messages from InputField also bubble up to
    ConversationManager automatically.
    """

    @property
    def scroll_view(self) -> "ScrollableContent":
        """Get the sibling scrollable content area."""
        from openhands_cli.tui.widgets.main_display import ScrollableContent

        # scroll_view is a sibling - query from parent (ConversationState)
        assert self.parent is not None, "InputAreaContainer must have a parent"
        return self.parent.query_one("#scroll_view", ScrollableContent)

    @on(SlashCommandSubmitted)
    def _on_slash_command_submitted(self, event: SlashCommandSubmitted) -> None:
        """Handle slash commands by routing to appropriate handlers.

        Routes to ConversationManager for conversation operations,
        or to app-level handlers for UI operations.
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
        from openhands_cli.tui.core import CreateConversation

        # Message bubbles up to ConversationManager (ancestor)
        self.post_message(CreateConversation())

    def _command_history(self) -> None:
        """Handle the /history command to show conversation history panel."""

        app = cast("OpenHandsApp", self.app)
        app.action_toggle_history()

    def _command_confirm(self) -> None:
        """Handle the /confirm command to show confirmation settings modal."""
        from openhands_cli.tui.core import SetConfirmationPolicy
        from openhands_cli.tui.modals.confirmation_modal import (
            ConfirmationSettingsModal,
        )

        app = cast("OpenHandsApp", self.app)

        # Get current confirmation policy from state
        current_policy = app.conversation_state.confirmation_policy

        # Callback posts message that bubbles up to ConversationManager
        def on_policy_selected(policy):
            self.post_message(SetConfirmationPolicy(policy))

        confirmation_modal = ConfirmationSettingsModal(
            current_policy=current_policy,
            on_policy_selected=on_policy_selected,
        )
        app.push_screen(confirmation_modal)

    def _command_condense(self) -> None:
        """Handle the /condense command to condense conversation history."""
        from openhands_cli.tui.core import CondenseConversation

        # Message bubbles up to ConversationManager (ancestor)
        self.post_message(CondenseConversation())

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

        app = cast("OpenHandsApp", self.app)

        if app.exit_confirmation:
            app.push_screen(ExitConfirmationModal())
        else:
            app.exit()
