from unittest import mock

from openhands.sdk import MessageEvent
from openhands_cli.conversations import viewer


class TestViewer:
    def test_view_conversation_not_found(self):
        with mock.patch(
            "openhands_cli.conversations.viewer.LocalFileStore"
        ) as MockStore:
            MockStore.return_value.exists.return_value = False

            with mock.patch(
                "openhands_cli.conversations.viewer.console"
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
            "openhands_cli.conversations.viewer.LocalFileStore"
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

            with mock.patch("openhands_cli.conversations.viewer.console"):
                # We mock DefaultConversationVisualizer to verify it's used
                with mock.patch(
                    "openhands_cli.conversations.viewer.DefaultConversationVisualizer"
                ) as MockVisualizer:
                    result = viewer.view_conversation("exists-id")
                    assert result is True

                    # Verify visualizer was called
                    MockVisualizer.return_value.on_event.assert_called()

    def test_view_conversation_handles_load_error(self):
        """Test that viewer handles errors during event loading gracefully."""
        with mock.patch(
            "openhands_cli.conversations.viewer.LocalFileStore"
        ) as MockStore:
            MockStore.return_value.exists.return_value = True

            # Create an iterator that yields one item then raises Exception
            def faulty_iterator():
                yield mock.Mock()  # one good event
                raise ValueError("Corrupt data")

            MockStore.return_value.load_events.return_value = faulty_iterator()

            with mock.patch(
                "openhands_cli.conversations.viewer.console"
            ) as mock_console:
                with mock.patch(
                    "openhands_cli.conversations.viewer.DefaultConversationVisualizer"
                ):
                    result = viewer.view_conversation("faulty-id")

                    # It should return True because one event was displayed
                    assert result is True

                    # Check that error was printed
                    error_printed = False
                    for call in mock_console.print.call_args_list:
                        if call.args and "Error loading events: Corrupt data" in str(
                            call.args[0]
                        ):
                            error_printed = True
                            break
                    assert error_printed
