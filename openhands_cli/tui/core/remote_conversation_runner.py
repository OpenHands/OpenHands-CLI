"""Remote conversation runner for OpenHands Cloud workspaces.

This module provides a specialized conversation runner for cloud-based
conversations that handles workspace lifecycle management, including
reconnection when the workspace becomes unresponsive.
"""

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from textual.message_pump import MessagePump
from textual.notifications import SeverityLevel

from openhands.sdk import Message, RemoteConversation
from openhands.sdk.event.base import Event
from openhands_cli.setup import setup_cloud_conversation
from openhands_cli.tui.core.conversation_runner import ConversationRunner
from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer


if TYPE_CHECKING:
    from openhands_cli.tui.core.state import ConversationContainer


class RemoteConversationRunner(ConversationRunner):
    """Conversation runner for OpenHands Cloud remote execution.

    Extends ConversationRunner with cloud-specific functionality:
    - Workspace health monitoring
    - Automatic workspace reconnection
    - Cloud-specific conversation setup

    This runner is used when `cloud=True` is passed to the RunnerFactory.
    """

    def __init__(
        self,
        conversation_id: uuid.UUID,
        state: "ConversationContainer",
        message_pump: MessagePump,
        notification_callback: Callable[[str, str, SeverityLevel], None],
        visualizer: ConversationVisualizer,
        event_callback: Callable[[Event], None] | None = None,
        *,
        server_url: str | None = None,
        sandbox_id: str | None = None,
    ):
        """Initialize the remote conversation runner.

        Args:
            conversation_id: UUID for the conversation.
            state: ConversationContainer for reading state and updating running status.
            message_pump: MessagePump (ConversationManager) for posting messages.
            notification_callback: Callback for notifications.
            visualizer: Visualizer for output display.
            event_callback: Optional callback for each event.
            server_url: The OpenHands Cloud server URL.
            sandbox_id: Optional sandbox ID to reclaim an existing sandbox.
        """
        # Store cloud configuration before calling parent __init__
        # These are needed for workspace reconnection
        self._server_url = server_url
        self._sandbox_id = sandbox_id
        self._conversation_id = conversation_id
        self._event_callback = event_callback

        # Store visualizer reference for reconnection
        self._visualizer = visualizer

        # Initialize base class - this will call _create_conversation
        # We need to set up the conversation ourselves since we're using cloud
        self.visualizer = visualizer
        self._running = False
        self._state = state
        self._message_pump = message_pump
        self._notification_callback = notification_callback

        # Create cloud conversation
        self.conversation = setup_cloud_conversation(
            conversation_id,
            confirmation_policy=state.confirmation_policy,
            visualizer=visualizer,
            event_callback=event_callback,
            server_url=server_url,
            sandbox_id=sandbox_id,
        )

        # Extract and store sandbox_id from the workspace for display
        self._update_sandbox_id_from_workspace()

    def _update_sandbox_id_from_workspace(self) -> None:
        """Extract sandbox_id from workspace and update state."""
        try:
            conversation = cast(RemoteConversation, self.conversation)
            workspace = conversation.workspace
            if workspace and hasattr(workspace, "sandbox_id") and workspace.sandbox_id:
                self._sandbox_id = workspace.sandbox_id
                self._state.set_sandbox_id(workspace.sandbox_id)
        except Exception:
            # Sandbox ID extraction is not critical, fail silently
            pass

    def _run_conversation_sync(self, message: Message, headless: bool = False) -> None:
        """Run the conversation synchronously in a thread.

        Overrides base class to add workspace health check before sending messages
        and handle cloud-specific errors gracefully.

        Args:
            message: The message to process
            headless: If True, print status to console
        """
        import httpx

        # Ensure cloud workspace is still alive before sending
        if not self._ensure_workspace_alive():
            return

        try:
            self.conversation.send_message(message)
            # Update sandbox_id after message is sent (sandbox starts on first message)
            self._update_sandbox_id_from_workspace()
            self._execute_remote_conversation(headless=headless)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            reason = e.response.reason_phrase
            self._notification_callback(
                "Cloud Error",
                f"Server returned error {status_code}: {reason}",
                "error",
            )
            self._update_run_status(False)
        except httpx.RequestError as e:
            self._notification_callback(
                "Network Error",
                f"Failed to communicate with cloud server: {e}",
                "error",
            )
            self._update_run_status(False)
        except Exception as e:
            self._notification_callback(
                "Unexpected Error",
                f"{type(e).__name__}: {e}",
                "error",
            )
            self._update_run_status(False)

    def _execute_remote_conversation(self, headless: bool = False) -> None:
        """Execute the remote conversation with proper status handling.

        Unlike local conversations where run() returns when the agent finishes,
        RemoteConversation.run() waits for terminal statuses (FINISHED, ERROR,
        STUCK). For interactive CLI use, we need to return when the agent goes
        IDLE (waiting for more input) after processing the current message.

        This method uses non-blocking run and polls for both terminal and IDLE
        statuses.
        """
        import time

        from rich.console import Console

        from openhands.sdk import ConversationExecutionStatus
        from openhands.sdk.conversation.exceptions import ConversationRunError

        self._update_run_status(True)

        try:
            conversation = cast(RemoteConversation, self.conversation)

            if headless:
                console = Console()
                console.print("Agent is working")

            # Use non-blocking run to trigger the agent on the server
            conversation.run(blocking=False)

            # Poll until agent finishes processing (IDLE) or hits terminal status
            poll_interval = 1.0
            timeout = 3600.0
            start_time = time.monotonic()

            while True:
                elapsed = time.monotonic() - start_time
                if elapsed > timeout:
                    raise ConversationRunError(
                        conversation._id,
                        TimeoutError(f"Run timed out after {timeout} seconds."),
                    )

                # Get current status from conversation state
                status = conversation.state.execution_status

                # Return on IDLE (agent finished current turn, waiting for input)
                if status == ConversationExecutionStatus.IDLE:
                    break

                # Return on terminal statuses
                if status in (
                    ConversationExecutionStatus.FINISHED,
                    ConversationExecutionStatus.PAUSED,
                    ConversationExecutionStatus.WAITING_FOR_CONFIRMATION,
                ):
                    break

                # Handle error states
                if status == ConversationExecutionStatus.ERROR:
                    raise ConversationRunError(
                        conversation._id,
                        RuntimeError("Remote conversation ended with error"),
                    )

                if status == ConversationExecutionStatus.STUCK:
                    raise ConversationRunError(
                        conversation._id,
                        RuntimeError("Remote conversation got stuck"),
                    )

                # Still running, wait before next poll
                time.sleep(poll_interval)

            if headless:
                console.print("Agent finished")

            # Check if confirmation needed
            if (
                self.is_confirmation_mode_active
                and conversation.state.execution_status
                == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
            ):
                self._request_confirmation()

        except ConversationRunError as e:
            self._notification_callback("Conversation Error", str(e), "error")
        except Exception as e:
            self._notification_callback(
                "Unexpected Error", f"{type(e).__name__}: {e}", "error"
            )
        finally:
            self._update_run_status(False)

    def _ensure_workspace_alive(self) -> bool:
        """Check if cloud workspace is alive and restart if needed.

        This method monitors the health of the cloud workspace and attempts
        to reconnect if the workspace becomes unresponsive. This can happen
        due to network issues, workspace timeouts, or other cloud-side problems.

        Returns:
            True if workspace is alive or was successfully reconnected,
            False if reconnection failed.
        """
        conversation = cast(RemoteConversation, self.conversation)
        workspace = conversation.workspace

        # Check if workspace is alive
        if workspace.alive:
            return True

        # Workspace is not responding, attempt reconnection
        self._notification_callback(
            "Workspace Reconnecting",
            "Cloud workspace is not responding. Attempting to reconnect...",
            "warning",
        )

        try:
            # Reinitialize the conversation with the same sandbox_id
            self.conversation = setup_cloud_conversation(
                self._conversation_id,
                confirmation_policy=self._state.confirmation_policy,
                visualizer=self._visualizer,
                event_callback=self._event_callback,
                server_url=self._server_url,
                sandbox_id=self._sandbox_id,
            )
            # Update sandbox_id in case it changed after reconnection
            self._update_sandbox_id_from_workspace()
            self._notification_callback(
                "Workspace Reconnected",
                "Cloud workspace has been reconnected successfully.",
                "information",
            )
            return True
        except Exception as e:
            self._notification_callback(
                "Workspace Error",
                f"Failed to reconnect to cloud workspace: {e}",
                "error",
            )
            return False
