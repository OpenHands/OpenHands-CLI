from datetime import UTC, datetime
from unittest import mock

from openhands_cli.conversations.cli import lister
from openhands_cli.conversations.models import ConversationMetadata


class TestLister:
    def test_display_recent_conversations_empty(self):
        with mock.patch(
            "openhands_cli.conversations.cli.lister.LocalFileStore"
        ) as MockStore:
            MockStore.return_value.list_conversations.return_value = []

            with mock.patch(
                "openhands_cli.conversations.cli.lister.console"
            ) as mock_console:
                lister.display_recent_conversations()

                # Should print "No conversations found"
                # Check call args
                found = False
                for call in mock_console.print.call_args_list:
                    if call.args and "No conversations found" in str(call.args[0]):
                        found = True
                        break
                assert found

    def test_display_recent_conversations_with_data(self):
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        convs = [
            ConversationMetadata(
                id="1234567890abcdef", created_at=now, title="Test Chat"
            ),
        ]

        with mock.patch(
            "openhands_cli.conversations.cli.lister.LocalFileStore"
        ) as MockStore:
            MockStore.return_value.list_conversations.return_value = convs

            with mock.patch(
                "openhands_cli.conversations.cli.lister.console"
            ) as mock_console:
                lister.display_recent_conversations()

                # Collect all printed text
                printed_text = ""
                for call in mock_console.print.call_args_list:
                    if call.args:
                        printed_text += str(call.args[0])

                assert "1234567890abcdef" in printed_text
                assert "Test Chat" in printed_text
