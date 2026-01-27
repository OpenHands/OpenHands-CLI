"""MainDisplay widget for rendering conversation content and handling commands.

This widget is the main conversation view that:
- Renders user messages when UserInputSubmitted is received
- Handles all slash commands via SlashCommandSubmitted
- Manages the conversation runner lifecycle
- Provides a scrollable view of the conversation

Widget Hierarchy:
    MainDisplay(VerticalScroll)
    ├── SplashBanner (data bound to conversation_id)
    ├── SplashVersion
    ├── SplashStatus
    ├── SplashConversation (data bound to conversation_id)
    ├── SplashInstructions
    ├── ... dynamically added conversation widgets
    └── AppState(#input_area)
        ├── WorkingStatusLine
        ├── InputField
        └── InfoStatusLine
"""

import asyncio
import uuid

from textual import on
from textual.containers import VerticalScroll
from textual.widgets import Static

from openhands_cli.tui.core.commands import show_help
from openhands_cli.tui.messages import SlashCommandSubmitted, UserInputSubmitted


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
        InputField → AppState → MainDisplay
        - UserInputSubmitted: Render message, then send to agent via App
        - SlashCommandSubmitted: Execute command (stop bubbling)
    """

    @on(UserInputSubmitted)
    async def on_user_input_submitted(self, event: UserInputSubmitted) -> None:
        """Handle user input by rendering it and sending to agent.

        1. Render the user message in the conversation view
        2. Delegate to App for agent processing

        We don't call event.stop() so the App can also handle it for
        agent processing.
        """
        # Render the user message
        user_message_widget = Static(
            f"> {event.content}", classes="user-message", markup=False
        )
        await self.mount(user_message_widget)
        self.scroll_end(animate=False)

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
        """Handle the /new command to start a new conversation."""
        from openhands_cli.tui.textual_app import OpenHandsApp

        app: OpenHandsApp = self.app  # type: ignore[assignment]

        # Check if a conversation is currently running
        if app.conversation_runner and app.conversation_runner.is_running:
            app.notify(
                title="New Conversation Error",
                message="Cannot start a new conversation while one is running. "
                "Please wait for the current conversation to complete or pause it.",
                severity="error",
            )
            return

        # Create a new conversation via store
        new_id_str = app._store.create()
        new_id = uuid.UUID(new_id_str)

        # Update AppState (single source of truth)
        app.conversation_id = new_id
        app.app_state.reset_conversation_state()

        # Reset the conversation runner
        app.conversation_runner = None

        # Remove any existing confirmation panel
        if app.confirmation_panel:
            app.confirmation_panel.remove()
            app.confirmation_panel = None

        # Clear all dynamically added widgets from main_display
        # Keep only the splash widgets and input_area
        widgets_to_remove = [
            w
            for w in self.children
            if not (w.id or "").startswith("splash_") and w.id != "input_area"
        ]
        for widget in widgets_to_remove:
            widget.remove()

        # Note: splash_conversation auto-updates via data binding to conversation_id
        # Scroll to top to show the splash screen
        self.scroll_home(animate=False)

        # Notify user
        app.notify(
            title="New Conversation",
            message="Started a new conversation",
            severity="information",
        )

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

        # Get current confirmation policy from AppState
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
