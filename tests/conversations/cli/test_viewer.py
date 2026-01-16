from unittest import mock

from openhands.sdk import MessageEvent
from openhands_cli.conversations.cli import viewer


class TestViewer:
    def test_view_conversation_not_found(self):
        with mock.patch(
            "openhands_cli.conversations.cli.viewer.LocalFileStore"
        ) as MockStore:
            MockStore.return_value.exists.return_value = False

            with mock.patch(
                "openhands_cli.conversations.cli.viewer.console"
            ) as mock_console:
                result = viewer.view_conversation("missing-id")
                assert result is False

                # Check error message
                found = False
                for call in mock_console.print.call_args_list:
                    if call.args and "Conversation not found: missing-id" in str(
                        call.args[0]
                    ):
                        found = True
                        break
                assert found

    def test_view_conversation_success(self):
        with mock.patch(
            "openhands_cli.conversations.cli.viewer.LocalFileStore"
        ) as MockStore:
            MockStore.return_value.exists.return_value = True

            # Mock load_events to return an iterator
            # MessageEvent schema: has llm_message
            event = MessageEvent(
                source="user",
                timestamp="2024-01-01T12:00:00Z",
                # type="message" is removed as it might be extra
                llm_message={"role": "user", "content": "Hello"},  # type: ignore
            )
            MockStore.return_value.load_events.return_value = iter([event])

            with mock.patch("openhands_cli.conversations.cli.viewer.console"):
                # We mock DefaultConversationVisualizer to verify it's used
                with mock.patch(
                    "openhands_cli.conversations.cli.viewer.DefaultConversationVisualizer"
                ) as MockVisualizer:
                    result = viewer.view_conversation("exists-id")
                    assert result is True

                    # Verify visualizer was called
                    MockVisualizer.return_value.on_event.assert_called()
