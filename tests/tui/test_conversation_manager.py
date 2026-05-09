from unittest.mock import MagicMock

from openhands_cli.tui.core.conversation_manager import ConversationManager
from openhands_cli.tui.core.state import ConversationContainer


def test_notification_callback_disables_markup(monkeypatch):
    manager = ConversationManager(
        ConversationContainer(),
        runner_factory=MagicMock(),
        store_service=MagicMock(),
    )

    notify = MagicMock()
    monkeypatch.setattr(manager, "notify", notify)

    manager._runners._notification_callback(
        "Conversation Error",
        "Expected markup value (found '={\\'command\\': foo}')",
        "error",
    )

    notify.assert_called_once_with(
        "Expected markup value (found '={\\'command\\': foo}')",
        title="Conversation Error",
        severity="error",
        markup=False,
    )
