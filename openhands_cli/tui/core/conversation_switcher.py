"""Conversation switching logic extracted from OpenHandsApp.

This class encapsulates all the complexity of switching between conversations:
- Loading notifications
- Thread coordination
- UI preparation and finalization
- Error handling
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from textual.notifications import Notification, Notify

from openhands_cli.tui.core.messages import (
    ConversationSwitched,
    RevertSelectionRequest,
)
from openhands_cli.tui.modals import SwitchConversationModal
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


if TYPE_CHECKING:
    from openhands_cli.tui.panels.conversation_pane import ConversationPane
    from openhands_cli.tui.textual_app import OpenHandsApp


class ConversationSwitcher:
    """Handles conversation switching with loading states and thread coordination.

    This class extracts ~180 lines of switching logic from OpenHandsApp,
    providing a single responsibility for all conversation switching concerns.
    """

    def __init__(self, app: OpenHandsApp):
        self.app = app
        self._loading_notification: Notification | None = None
        self._is_switching: bool = False

    @property
    def is_switching(self) -> bool:
        """Check if a conversation switch is in progress."""
        return self._is_switching

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
            # Revert selection highlight back to current conversation.
            self.app.post_message(RevertSelectionRequest())
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

        # Show a persistent loading notification
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
        self._is_switching = True

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
            self._is_switching = False

    def _prepare_ui(self, conversation_id: uuid.UUID) -> ConversationPane:
        """Prepare UI for switching conversations (runs on the UI thread).

        Returns the pane for the target conversation.
        """
        app = self.app

        # Set the conversation ID immediately
        app.conversation_id = conversation_id
        app.conversation_session_manager.set_active_conversation(conversation_id)
        app.conversation_runner = None

        # Remove any existing confirmation panel
        if app.confirmation_panel:
            app.confirmation_panel.remove()
            app.confirmation_panel = None

        # Switch to target pane (hides old pane, shows/creates new one)
        pane = app.switch_active_pane(conversation_id)

        return pane

    def _finish_switch(self, runner, target_id: uuid.UUID, pane) -> None:
        """Finalize conversation switch (runs on the UI thread)."""
        self.app.conversation_runner = runner
        pane.scroll_to_end()
        self._dismiss_loading()
        self.app.post_message(ConversationSwitched(target_id))
        self.app.notify(
            title="Switched",
            message=f"Resumed conversation {target_id.hex[:8]}",
            severity="information",
        )
        self.app.input_field.disabled = False
        self.app.input_field.focus_input()

    def _switch_thread(self, target_id: uuid.UUID) -> None:
        """Background thread worker for switching conversations.

        If we have a fully cached session (pane + runner), we do instant switch
        without loading from disk. Otherwise we load events and render.
        """
        try:
            # Check for fully cached session BEFORE preparing UI
            csm = self.app.conversation_session_manager
            cached_runner = csm.get_runner(target_id)
            has_full_cache = (
                csm.has_cached_pane(target_id) and cached_runner is not None
            )

            # Prepare UI (on main thread) - returns the pane
            pane: ConversationPane = self.app.call_from_thread(
                self._prepare_ui, target_id
            )

            if has_full_cache and pane.is_rendered:
                # Full cache hit! Instant switch - no disk loading.
                # Just reuse cached runner.
                self.app.call_from_thread(
                    self._finish_switch, cached_runner, target_id, pane
                )
                return

            # Cache miss - need to load and render.
            # Create visualizer targeting pane's content_container.
            def _create_visualizer():
                return ConversationVisualizer(
                    pane.content_container, self.app, skip_user_messages=True
                )

            visualizer = self.app.call_from_thread(_create_visualizer)

            # Create runner (loads events from disk)
            runner = self.app.create_conversation_runner(
                conversation_id=target_id, visualizer=visualizer
            )

            # Get events and render (only if pane not already rendered)
            if not pane.is_rendered:
                events = (
                    list(runner.conversation.state.events)
                    if runner.conversation.state
                    else []
                )
                if events:
                    self.app.call_from_thread(pane.render_history, events, visualizer)

            # Finalize on UI thread
            self.app.call_from_thread(self._finish_switch, runner, target_id, pane)
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
