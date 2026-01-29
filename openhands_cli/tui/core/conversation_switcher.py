"""Conversation switching logic extracted from OpenHandsApp.

This class encapsulates all the complexity of switching between conversations:
- Loading notifications
- Thread coordination
- UI preparation and finalization
- Error handling

State changes are made via ConversationView, which UI components watch for updates.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from textual.notifications import Notification, Notify

from openhands_cli.tui.modals import SwitchConversationModal


if TYPE_CHECKING:
    from openhands_cli.tui.textual_app import OpenHandsApp


class ConversationSwitcher:
    """Handles conversation switching with loading states and thread coordination.

    This class extracts ~180 lines of switching logic from OpenHandsApp,
    providing a single responsibility for all conversation switching concerns.
    """

    def __init__(self, app: OpenHandsApp):
        self.app = app
        self._loading_notification: Notification | None = None

    def switch_to(self, conversation_id: str) -> None:
        """Switch to an existing local conversation.

        This is the main entry point for conversation switching.
        Handles validation, confirmation modals, and delegates to internal methods.

        Args:
            conversation_id: The conversation ID to switch to
        """
        try:
            target_id = uuid.UUID(conversation_id)
        except ValueError:
            self.app.notify(
                title="Switch Error",
                message="Invalid conversation id.",
                severity="error",
            )
            return

        # If an agent is currently running, confirm before switching.
        if self.app.conversation_runner and self.app.conversation_runner.is_running:
            self.app.push_screen(
                SwitchConversationModal(
                    prompt=(
                        "The agent is still running.\n\n"
                        "Switching conversations will pause the current run.\n"
                        "Do you want to switch anyway?"
                    )
                ),
                lambda confirmed: self._handle_confirmation(confirmed, target_id),
            )
            return

        self._perform_switch(target_id)

    def _handle_confirmation(
        self, confirmed: bool | None, target_id: uuid.UUID
    ) -> None:
        """Handle the result of the switch conversation confirmation modal."""
        if confirmed:
            self._switch_with_pause(target_id)
        else:
            # Revert selection - set is_switching to False triggers UI update
            self.app.conversation_view.finish_switching()
            self.app.input_field.focus_input()

    def _switch_with_pause(self, target_id: uuid.UUID) -> None:
        """Switch conversations, pausing the current run if needed."""
        # Disable input during switch to prevent user interaction
        self.app.input_field.disabled = True

        def _pause_if_running() -> None:
            runner = self.app.conversation_runner
            if runner and runner.is_running:
                runner.conversation.pause()

        self._perform_switch(target_id, pre_switch_action=_pause_if_running)

    def _perform_switch(
        self,
        target_id: uuid.UUID,
        pre_switch_action: Callable[[], None] | None = None,
    ) -> None:
        """Common logic for switching conversations.

        Args:
            target_id: The conversation ID to switch to
            pre_switch_action: Optional action to run before switch (e.g., pause)
        """
        # Don't switch if already on this conversation
        if self.app.conversation_id == target_id:
            self.app.notify(
                title="Already Active",
                message="This conversation is already active.",
                severity="information",
            )
            return

        # Show a persistent loading notification and mark switching in progress
        self._show_loading()

        def _worker() -> None:
            if pre_switch_action:
                try:
                    pre_switch_action()
                except Exception:
                    pass  # Don't block switch on pre-action failure
            self._switch_thread(target_id)

        self.app.run_worker(
            _worker,
            name="switch_conversation",
            group="switch_conversation",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _show_loading(self) -> None:
        """Show a loading notification that can be dismissed after the switch."""
        # Mark switching in progress via ConversationView
        self.app.conversation_view.start_switching()

        # Dismiss any previous loading notification
        if self._loading_notification is not None:
            try:
                self.app._unnotify(self._loading_notification)
            except Exception:
                pass
            self._loading_notification = None

        notification = Notification(
            "⏳ Switching conversation...",
            title="Switching",
            severity="information",
            timeout=3600,
            markup=True,
        )
        self._loading_notification = notification
        self.app.post_message(Notify(notification))

    def _dismiss_loading(self) -> None:
        """Dismiss the switch loading notification if present."""
        if self._loading_notification is None:
            return
        try:
            self.app._unnotify(self._loading_notification)
        finally:
            self._loading_notification = None
            # Mark switching complete via ConversationView
            self.app.conversation_view.finish_switching()

    def _prepare_ui(self, conversation_id: uuid.UUID) -> None:
        """Prepare UI for switching conversations (runs on the UI thread)."""
        app = self.app

        # Set the conversation ID - triggers reactive updates:
        # - ConversationView.watch_conversation_id() clears dynamic content
        # - SplashContent.watch_conversation_id() re-renders
        app.conversation_id = conversation_id
        app.conversation_runner = None

        # Remove any existing confirmation panel
        if app.confirmation_panel:
            app.confirmation_panel.remove()
            app.confirmation_panel = None

    def _finish_switch(self, runner, target_id: uuid.UUID) -> None:
        """Finalize conversation switch (runs on the UI thread)."""
        self.app.conversation_runner = runner
        self.app.scroll_view.scroll_end(animate=False)
        self._dismiss_loading()

        # Update ConversationView - UI components will react automatically
        self.app.conversation_id = target_id
        # Reset running state, metrics, etc.
        self.app.conversation_view.reset_conversation_state()

        self.app.notify(
            title="Switched",
            message=f"Resumed conversation {target_id.hex[:8]}",
            severity="information",
        )
        self.app.input_field.disabled = False
        self.app.input_field.focus_input()

    def _switch_thread(self, target_id: uuid.UUID) -> None:
        """Background thread worker for switching conversations."""
        try:
            # Prepare UI first (on main thread)
            self.app.call_from_thread(self._prepare_ui, target_id)

            # Set the new conversation_id on ConversationView and create runner
            # This needs to be done on the main thread since it modifies state
            def _create_runner_for_conversation() -> None:
                self.app.conversation_view.conversation_id = target_id
                # Force creation of new runner for this conversation
                self.app.conversation_view.conversation_runner = None
                runner = self.app.conversation_view.get_or_create_runner()
                self._finish_switch(runner, target_id)

            self.app.call_from_thread(_create_runner_for_conversation)
        except Exception as e:
            error_message = f"{type(e).__name__}: {e}"

            def _show_error() -> None:
                self._dismiss_loading()
                self.app.notify(
                    title="Switch Error",
                    message=error_message,
                    severity="error",
                )

            self.app.call_from_thread(_show_error)
