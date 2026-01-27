"""MainDisplay widget for rendering conversation content and handling commands.

This widget is the main conversation view that:
- Renders user messages when UserInputSubmitted is received
- Handles all slash commands via SlashCommandSubmitted
- Manages the conversation runner lifecycle
- Provides a scrollable view of the conversation

Widget Hierarchy:
    MainDisplay(VerticalScroll)
    ├── SplashContent(#splash_content)   ← data_bind to is_ui_ready, conversation_id
    │   ├── Static(#splash_banner)
    │   ├── Static(#splash_version)
    │   ├── Static(#splash_status)
    │   ├── Static(#splash_conversation)
    │   ├── Static(#splash_instructions_header)
    │   ├── Static(#splash_instructions)
    │   ├── Static(#splash_update_notice)
    │   └── Static(#splash_critic_notice)
    ├── ... dynamically added conversation widgets
    └── InputAreaContainer(#input_area)
        ├── WorkingStatusLine
        ├── InputField
        └── InfoStatusLine
"""

import asyncio
import uuid

from textual import on
from textual.containers import VerticalScroll
from textual.reactive import var
from textual.widgets import Static

from openhands_cli.tui.core.commands import show_help
from openhands_cli.tui.messages import (
    NewConversationRequested,
    ProcessUserInput,
    SlashCommandSubmitted,
    UserInputSubmitted,
)


class MainDisplay(VerticalScroll):
    """Scrollable conversation display that handles user input and commands.

    MainDisplay is responsible for:
    - Rendering user messages (UserInputSubmitted)
    - Executing slash commands (SlashCommandSubmitted)
    - Managing conversation content (clear, help display)
    - Scrolling and navigation

    It delegates to self.app for:
    - Conversation runner management (owned by App)
    - Screen/modal pushing (exit, confirm, settings)
    - Side panel toggling (history)
    - Notifications

    Message Flow:
        InputField → ConversationView → MainDisplay
        - UserInputSubmitted: Render message, then send to agent via App
        - SlashCommandSubmitted: Execute command (stop bubbling)

    Reactive Properties (via data_bind from ConversationView):
        - running: Whether a conversation is currently running
        - conversation_id: Current conversation ID (clears content on change)
    """

    # Reactive properties bound via data_bind() to ConversationView
    running: var[bool] = var(False)
    conversation_id: var[uuid.UUID] = var(uuid.uuid4)

    def watch_conversation_id(
        self, old_id: uuid.UUID, new_id: uuid.UUID
    ) -> None:
        """Clear dynamic content when conversation changes.

        When conversation_id changes, removes all dynamically added widgets
        (user messages, agent responses, etc.) while preserving:
        - SplashContent (#splash_content) - re-renders via its own binding
        - InputAreaContainer (#input_area) - always visible at bottom
        """
        if old_id == new_id:
            return

        # Remove all children except permanent widgets
        for widget in list(self.children):
            if widget.id not in ("splash_content", "input_area"):
                widget.remove()

        # Scroll to top to show splash screen
        self.scroll_home(animate=False)

    @on(UserInputSubmitted)
    async def on_user_input_submitted(self, event: UserInputSubmitted) -> None:
        """Handle user input by rendering it and posting for processing.

        This handles both typed inputs (from InputField) and queued inputs
        (from --task/--file via App._process_queued_inputs).

        Flow:
        1. Stop event propagation (MainDisplay fully handles this)
        2. Render the user message in the display
        3. Post ProcessUserInput to ConversationView for agent processing
        """
        event.stop()

        # Render the user message
        user_message_widget = Static(
            f"> {event.content}", classes="user-message", markup=False
        )
        await self.mount(user_message_widget)
        self.scroll_end(animate=False)

        # Post to ConversationView for processing with the runner
        self.post_message(ProcessUserInput(content=event.content))

    @on(SlashCommandSubmitted)
    def on_slash_command_submitted(self, event: SlashCommandSubmitted) -> None:
        """Handle slash commands.

        Routes to appropriate _command_* method based on the command.
        Stops event propagation since MainDisplay handles all commands.
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
        show_help(self)

    def _command_new(self) -> None:
        """Handle the /new command to start a new conversation.

        Posts NewConversationRequested message to ConversationView which owns
        the conversation lifecycle. ConversationView will:
        - Check if conversation is running
        - Create new conversation ID
        - Reset state
        - Clear UI
        """
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
        current_policy = app.app_state.confirmation_policy

        # Show the confirmation settings modal
        confirmation_modal = ConfirmationSettingsModal(
            current_policy=current_policy,
            on_policy_selected=app.app_state.set_confirmation_policy,
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
