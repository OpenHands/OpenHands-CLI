"""Command definitions and handlers for OpenHands CLI.

This module contains all available commands, their descriptions,
and the logic for handling command execution.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from textual.containers import VerticalScroll
from textual.widgets import Static
from textual_autocomplete import DropdownItem

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.splash import get_conversation_text


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp


# Available commands with descriptions after the command
COMMANDS = [
    DropdownItem(main="/help - Display available commands"),
    DropdownItem(main="/new - Start a new conversation"),
    DropdownItem(main="/history - Toggle conversation history"),
    DropdownItem(main="/confirm - Configure confirmation settings"),
    DropdownItem(main="/condense - Condense conversation history"),
    DropdownItem(main="/feedback - Send anonymous feedback about CLI"),
    DropdownItem(main="/exit - Exit the application"),
]


def get_valid_commands() -> set[str]:
    """Extract valid command names from COMMANDS list.

    Returns:
        Set of valid command strings (e.g., {"/help", "/exit"})
    """
    valid_commands = set()
    for command_item in COMMANDS:
        command_text = str(command_item.main)
        # Extract command part (before " - " if present)
        if " - " in command_text:
            command = command_text.split(" - ")[0]
        else:
            command = command_text
        valid_commands.add(command)
    return valid_commands


def is_valid_command(user_input: str) -> bool:
    """Check if user input is an exact match for a valid command.

    Args:
        user_input: The user's input string

    Returns:
        True if input exactly matches a valid command, False otherwise
    """
    return user_input in get_valid_commands()


def show_help(main_display: VerticalScroll) -> None:
    """Display help information in the main display.

    Args:
        main_display: The VerticalScroll widget to mount help content to
    """
    primary = OPENHANDS_THEME.primary
    secondary = OPENHANDS_THEME.secondary

    help_text = f"""
[bold {primary}]OpenHands CLI Help[/bold {primary}]
[dim]Available commands:[/dim]

  [{secondary}]/help[/{secondary}] - Display available commands
  [{secondary}]/new[/{secondary}] - Start a new conversation
  [{secondary}]/history[/{secondary}] - Toggle conversation history
  [{secondary}]/confirm[/{secondary}] - Configure confirmation settings
  [{secondary}]/condense[/{secondary}] - Condense conversation history
  [{secondary}]/feedback[/{secondary}] - Send anonymous feedback about CLI
  [{secondary}]/exit[/{secondary}] - Exit the application

[dim]Tips:[/dim]
  • Type / and press Tab to see command suggestions
  • Use arrow keys to navigate through suggestions
  • Press Enter to select a command
"""
    help_widget = Static(help_text, classes="help-message")
    main_display.mount(help_widget)


class CommandHandler:
    """Handles command execution for the OpenHands CLI app.

    This class encapsulates all command handling logic, delegating to the app
    for UI operations and state management.
    """

    def __init__(self, app: OpenHandsApp) -> None:
        """Initialize the command handler.

        Args:
            app: The OpenHands app instance to delegate UI operations to.
        """
        self._app = app

    def handle_command(self, command: str) -> None:
        """Handle command execution by dispatching to the appropriate handler.

        Args:
            command: The command string to execute (e.g., "/help", "/exit").
        """
        if command == "/help":
            self._handle_help()
        elif command == "/new":
            self._handle_new()
        elif command == "/history":
            self._handle_history()
        elif command == "/confirm":
            self._handle_confirm()
        elif command == "/condense":
            self._handle_condense()
        elif command == "/feedback":
            self._handle_feedback()
        elif command == "/exit":
            self._handle_exit()
        else:
            self._app.notify(
                title="Command error",
                message=f"Unknown command: {command}",
                severity="error",
            )

    def _handle_help(self) -> None:
        """Handle the /help command to display available commands."""
        show_help(self._app.main_display)

    def _handle_new(self) -> None:
        """Handle the /new command to start a new conversation."""
        app = self._app

        # Check if a conversation is currently running
        if app.conversation_runner and app.conversation_runner.is_running:
            app.notify(
                title="New Conversation Error",
                message="Cannot start a new conversation while one is running. "
                "Please wait for the current conversation to complete or pause it.",
                severity="error",
            )
            return None

        # Create a new conversation via store
        new_id_str = app._store.create()
        new_id = uuid.UUID(new_id_str)

        # Update AppState (single source of truth) - UI components react automatically
        # conversation_id property delegates to app_state
        app.conversation_id = new_id
        app.app_state.reset_conversation_state()  # Reset running state, metrics, etc.

        # Reset the conversation runner
        app.conversation_runner = None

        # Remove any existing confirmation panel
        if app.confirmation_panel:
            app.confirmation_panel.remove()
            app.confirmation_panel = None

        # Clear all dynamically added widgets from main_display
        # Keep only the splash widgets (those with IDs starting with "splash_")
        widgets_to_remove = [
            w
            for w in app.main_display.children
            if not (w.id or "").startswith("splash_")
        ]
        for widget in widgets_to_remove:
            widget.remove()

        # Update the splash conversation widget with the new conversation ID
        splash_conversation = app.query_one("#splash_conversation", Static)
        splash_conversation.update(
            get_conversation_text(new_id.hex, theme=OPENHANDS_THEME)
        )

        # Scroll to top to show the splash screen
        app.main_display.scroll_home(animate=False)

        # Notify user
        app.notify(
            title="New Conversation",
            message="Started a new conversation",
            severity="information",
        )

    def _handle_history(self) -> None:
        """Handle the /history command to show conversation history panel."""
        self._app.action_toggle_history()

    def _handle_confirm(self) -> None:
        """Handle the /confirm command to show confirmation settings modal."""
        from openhands_cli.tui.modals.confirmation_modal import (
            ConfirmationSettingsModal,
        )

        # Get current confirmation policy from StateManager (it owns the policy)
        current_policy = self._app.app_state.confirmation_policy

        # Show the confirmation settings modal
        # Pass StateManager's set_confirmation_policy directly - modal handles notification
        confirmation_modal = ConfirmationSettingsModal(
            current_policy=current_policy,
            on_policy_selected=self._app.app_state.set_confirmation_policy,
        )
        self._app.push_screen(confirmation_modal)

    def _handle_condense(self) -> None:
        """Handle the /condense command to condense conversation history."""
        if not self._app.conversation_runner:
            self._app.notify(
                title="Condense Error",
                message="No conversation available to condense",
                severity="error",
            )
            return

        # Use the async condensation method from conversation runner
        # This will handle all error cases and notifications
        asyncio.create_task(self._app.conversation_runner.condense_async())

    def _handle_feedback(self) -> None:
        """Handle the /feedback command to open feedback form in browser."""
        import webbrowser

        feedback_url = "https://forms.gle/chHc5VdS3wty5DwW6"
        webbrowser.open(feedback_url)
        self._app.notify(
            title="Feedback",
            message="Opening feedback form in your browser...",
            severity="information",
        )

    def _handle_exit(self) -> None:
        """Handle the /exit command with optional confirmation."""
        from openhands_cli.tui.modals.exit_modal import ExitConfirmationModal

        if self._app.exit_confirmation:
            self._app.push_screen(ExitConfirmationModal())
        else:
            self._app.exit()
