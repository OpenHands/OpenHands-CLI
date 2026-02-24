"""RunnerFactory - builds ConversationRunner instances with required dependencies.

This module exists to keep ConversationManager lightweight.
It creates either a local ConversationRunner or a RemoteConversationRunner
based on the cloud mode setting.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from textual.message_pump import MessagePump
from textual.notifications import SeverityLevel

from openhands.sdk.event.base import Event
from openhands_cli.tui.widgets.richlog_visualizer import (
    DEFAULT_AGENT_NAME,
)


if TYPE_CHECKING:
    from openhands_cli.tui.core.conversation_runner import ConversationRunner
    from openhands_cli.tui.core.state import ConversationContainer
    from openhands_cli.tui.textual_app import OpenHandsApp
    from openhands_cli.tui.widgets.main_display import ScrollableContent


NotificationCallback = Callable[[str, str, SeverityLevel], None]
ScrollViewProvider = Callable[[], "ScrollableContent"]
AppProvider = Callable[[], "OpenHandsApp"]


class RunnerFactory:
    """Factory for creating conversation runners.

    Creates either a local ConversationRunner or a RemoteConversationRunner
    based on the cloud mode setting.
    """

    def __init__(
        self,
        *,
        state: ConversationContainer,
        app_provider: AppProvider,
        scroll_view_provider: ScrollViewProvider,
        json_mode: bool,
        env_overrides_enabled: bool,
        critic_disabled: bool,
        cloud: bool = False,
        server_url: str | None = None,
        sandbox_id: str | None = None,
    ) -> None:
        self._state = state
        self._app_provider = app_provider
        self._scroll_view_provider = scroll_view_provider
        self._json_mode = json_mode
        self._env_overrides_enabled = env_overrides_enabled
        self._critic_disabled = critic_disabled
        self._cloud = cloud
        self._server_url = server_url
        self._sandbox_id = sandbox_id

    def create(
        self,
        conversation_id: uuid.UUID,
        *,
        message_pump: MessagePump,
        notification_callback: NotificationCallback,
    ) -> ConversationRunner:
        """Create a conversation runner.

        Returns a RemoteConversationRunner if cloud mode is enabled,
        otherwise returns a local ConversationRunner.
        """
        from openhands_cli.tui.widgets.richlog_visualizer import ConversationVisualizer
        from openhands_cli.utils import json_callback

        app = self._app_provider()

        # Visualizer reads cli_settings directly when needed via self.cli_settings
        visualizer = ConversationVisualizer(
            self._scroll_view_provider(),
            app,
            name=DEFAULT_AGENT_NAME,
        )

        event_callback: Callable[[Event], None] | None = (
            json_callback if self._json_mode else None
        )

        if self._cloud:
            runner = self._create_remote_runner(
                conversation_id,
                message_pump=message_pump,
                notification_callback=notification_callback,
                visualizer=visualizer,
                event_callback=event_callback,
            )
        else:
            runner = self._create_local_runner(
                conversation_id,
                message_pump=message_pump,
                notification_callback=notification_callback,
                visualizer=visualizer,
                event_callback=event_callback,
            )

        # Attach conversation to state for metrics reading
        self._state.attach_conversation_state(runner.conversation.state)
        return runner

    def _create_local_runner(
        self,
        conversation_id: uuid.UUID,
        *,
        message_pump: MessagePump,
        notification_callback: NotificationCallback,
        visualizer: ConversationVisualizer,
        event_callback: Callable[[Event], None] | None,
    ) -> ConversationRunner:
        """Create a local conversation runner."""
        from openhands_cli.tui.core.conversation_runner import ConversationRunner

        return ConversationRunner(
            conversation_id,
            state=self._state,
            message_pump=message_pump,
            notification_callback=notification_callback,
            visualizer=visualizer,
            event_callback=event_callback,
            env_overrides_enabled=self._env_overrides_enabled,
            critic_disabled=self._critic_disabled,
        )

    def _create_remote_runner(
        self,
        conversation_id: uuid.UUID,
        *,
        message_pump: MessagePump,
        notification_callback: NotificationCallback,
        visualizer: ConversationVisualizer,
        event_callback: Callable[[Event], None] | None,
    ) -> ConversationRunner:
        """Create a remote conversation runner for cloud mode."""
        from openhands_cli.tui.core.remote_conversation_runner import (
            RemoteConversationRunner,
        )

        return RemoteConversationRunner(
            conversation_id,
            state=self._state,
            message_pump=message_pump,
            notification_callback=notification_callback,
            visualizer=visualizer,
            event_callback=event_callback,
            server_url=self._server_url,
            sandbox_id=self._sandbox_id,
        )
