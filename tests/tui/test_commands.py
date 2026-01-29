"""Tests for the commands module."""

import uuid
from datetime import UTC, datetime
from typing import cast
from unittest import mock

import pytest
from textual.containers import VerticalScroll
from textual_autocomplete import DropdownItem

from openhands.sdk.security.confirmation_policy import AlwaysConfirm
from openhands_cli.conversations.models import ConversationMetadata
from openhands_cli.conversations.store.local import LocalFileStore
from openhands_cli.tui.core.commands import COMMANDS, is_valid_command, show_help
from openhands_cli.tui.modals import SettingsScreen
from openhands_cli.tui.modals.confirmation_modal import (
    ConfirmationSettingsModal,
)
from openhands_cli.tui.modals.exit_modal import ExitConfirmationModal
from openhands_cli.tui.modals.switch_conversation_modal import SwitchConversationModal
from openhands_cli.tui.panels.history_side_panel import HistoryItem, HistorySidePanel
from openhands_cli.tui.textual_app import OpenHandsApp


class TestCommands:
    """Tests for command definitions and handlers."""

    def test_commands_list_structure(self):
        """Test that COMMANDS list has correct structure."""
        assert isinstance(COMMANDS, list)
        assert len(COMMANDS) == 7

        # Check that all items are DropdownItems
        for command in COMMANDS:
            assert isinstance(command, DropdownItem)
            assert hasattr(command, "main")
            # main is a Content object, not a string
            assert hasattr(command.main, "__str__")

    @pytest.mark.parametrize(
        "expected_command,expected_description",
        [
            ("/help", "Display available commands"),
            ("/new", "Start a new conversation"),
            ("/history", "Toggle conversation history"),
            ("/confirm", "Configure confirmation settings"),
            ("/condense", "Condense conversation history"),
            ("/feedback", "Send anonymous feedback about CLI"),
            ("/exit", "Exit the application"),
        ],
    )
    def test_commands_content(self, expected_command, expected_description):
        """Test that commands contain expected content."""
        command_strings = [str(cmd.main) for cmd in COMMANDS]

        # Find the command that starts with expected_command
        matching_command = None
        for cmd_str in command_strings:
            if cmd_str.startswith(expected_command):
                matching_command = cmd_str
                break

        assert matching_command is not None, f"Command {expected_command} not found"
        assert expected_description in matching_command
        assert " - " in matching_command  # Should have separator

    def test_show_help_function_signature(self):
        """Test that show_help has correct function signature."""
        import inspect

        sig = inspect.signature(show_help)
        params = list(sig.parameters.keys())

        assert len(params) == 1
        assert params[0] == "scroll_view"

    @pytest.mark.parametrize(
        "expected_content",
        [
            "OpenHands CLI Help",
            "/help",
            "/new",
            "/history",
            "/confirm",
            "/condense",
            "/feedback",
            "/exit",
            "Display available commands",
            "Start a new conversation",
            "Toggle conversation history",
            "Configure confirmation settings",
            "Condense conversation history",
            "Send anonymous feedback about CLI",
            "Exit the application",
            "Tips:",
            "Type / and press Tab",
            "Use arrow keys to navigate",
            "Press Enter to select",
        ],
    )
    def test_show_help_content_elements(self, expected_content):
        """Test that show_help includes all expected content elements."""
        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        show_help(mock_main_display)

        # Get the help text that was mounted
        mock_main_display.mount.assert_called_once()
        help_widget = mock_main_display.mount.call_args[0][0]
        help_text = help_widget.content

        assert expected_content in help_text

    def test_show_help_uses_theme_colors(self):
        """Test that show_help uses OpenHands theme colors."""
        from openhands_cli.theme import OPENHANDS_THEME

        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        show_help(mock_main_display)

        help_widget = mock_main_display.mount.call_args[0][0]
        help_text = help_widget.content

        # Should use OpenHands theme colors
        assert OPENHANDS_THEME.primary in help_text  # Primary color (yellow)
        assert OPENHANDS_THEME.secondary in help_text  # Secondary color (white)

        # Should not use generic color names
        assert "yellow" not in help_text.lower()
        assert "white" not in help_text.lower()

    def test_show_help_formatting(self):
        """Test that show_help has proper Rich markup formatting."""
        from openhands_cli.theme import OPENHANDS_THEME

        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        show_help(mock_main_display)

        help_widget = mock_main_display.mount.call_args[0][0]
        help_text = help_widget.content

        # Check for proper Rich markup with theme colors
        assert f"[bold {OPENHANDS_THEME.primary}]" in help_text
        assert f"[/bold {OPENHANDS_THEME.primary}]" in help_text
        assert f"[{OPENHANDS_THEME.secondary}]" in help_text
        assert f"[/{OPENHANDS_THEME.secondary}]" in help_text
        assert "[dim]" in help_text

        # Should start and end with newlines for proper spacing
        assert help_text.startswith("\n")
        assert help_text.endswith("\n")

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("/help", True),
            ("/new", True),
            ("/history", True),
            ("/confirm", True),
            ("/condense", True),
            ("/feedback", True),
            ("/exit", True),
            ("/help extra", False),
            ("/exit now", False),
            ("/unknown", False),
            ("/", False),
            ("help", False),
            ("", False),
        ],
    )
    def test_is_valid_command(self, cmd, expected):
        """Command validation is strict and argument-sensitive."""
        assert is_valid_command(cmd) is expected

    def test_commands_contains_history(self):
        """Test COMMANDS includes /history."""
        command_names = [str(cmd.main).split(" - ")[0] for cmd in COMMANDS]

        assert "/history" in command_names
        assert "/help" in command_names
        assert "/new" in command_names
        assert len(COMMANDS) == 7

    def test_all_commands_included_in_help(self):
        """Test that all commands from COMMANDS list are included in help text.

        This ensures that when new commands are added to COMMANDS, they are also
        added to the help text displayed by show_help().
        """
        from openhands_cli.tui.core.commands import get_valid_commands

        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        show_help(mock_main_display)

        # Get the help text that was mounted
        mock_main_display.mount.assert_called_once()
        help_widget = mock_main_display.mount.call_args[0][0]
        help_text = help_widget.content

        # Get all valid commands from COMMANDS list
        valid_commands = get_valid_commands()

        # Verify each command is present in the help text
        missing_commands = []
        for command in valid_commands:
            if command not in help_text:
                missing_commands.append(command)

        assert not missing_commands, (
            f"The following commands are defined in COMMANDS but missing from "
            f"help text: {missing_commands}"
        )


class TestOpenHandsAppCommands:
    """Integration-style tests for command handling in OpenHandsApp."""

    @pytest.mark.asyncio
    async def test_confirm_command_opens_confirmation_settings_modal(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/confirm` should open ConfirmationSettingsModal.

        Note: The app reads the policy from conversation_view.confirmation_policy
        (ConversationView owns the policy), not from conversation_runner.
        """
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=True)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Verify conversation_view has the default policy
            assert isinstance(
                oh_app.conversation_view.confirmation_policy, AlwaysConfirm
            )

            oh_app.conversation_view.input_area._command_confirm()

            top_screen = oh_app.screen_stack[-1]
            assert isinstance(top_screen, ConfirmationSettingsModal)

    @pytest.mark.asyncio
    async def test_exit_command_opens_exit_confirmation_modal_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/exit` should open ExitConfirmationModal when exit_confirmation is True."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=True)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            oh_app.conversation_view.input_area._command_exit()

            top_screen = oh_app.screen_stack[-1]
            assert isinstance(top_screen, ExitConfirmationModal)

    @pytest.mark.asyncio
    async def test_exit_command_exits_immediately_when_confirmation_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/exit` should call app.exit() directly when exit_confirmation is False."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Replace exit with a MagicMock so we can assert it was called
            exit_mock = mock.MagicMock()
            oh_app.exit = exit_mock

            oh_app.conversation_view.input_area._command_exit()

            exit_mock.assert_called_once_with()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "has_runner,runner_running,expected_notification",
        [
            (False, False, "Condense Error"),  # No conversation runner
            (True, True, None),  # Runner exists but is running (handled by runner)
            (True, False, None),  # Runner exists and not running (success case)
        ],
    )
    async def test_condense_command_scenarios(
        self,
        monkeypatch: pytest.MonkeyPatch,
        has_runner: bool,
        runner_running: bool,
        expected_notification: str | None,
    ) -> None:
        """`/condense` should handle different conversation runner states correctly."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        # Mock the notify method to capture notifications
        notify_mock = mock.MagicMock()

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)
            oh_app.notify = notify_mock

            dummy_runner = None
            if has_runner:
                # Create a mock conversation runner
                dummy_runner = mock.MagicMock()
                dummy_runner.is_running = runner_running
                dummy_runner.condense_async = mock.AsyncMock()
                oh_app.conversation_runner = dummy_runner
            else:
                oh_app.conversation_runner = None

            oh_app.conversation_view.input_area._command_condense()

            if expected_notification:
                # Should have called notify with error
                notify_mock.assert_called_once()
                call_args = notify_mock.call_args
                assert call_args[1]["title"] == expected_notification
            elif has_runner and dummy_runner is not None:
                # Should have called condense_async
                dummy_runner.condense_async.assert_called_once()
                # Should not have called notify (error handling is in runner)
                notify_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_condense_command_calls_async_method(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/condense` should call the async condense method on conversation runner."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Create a mock conversation runner with async condense method
            dummy_runner = mock.MagicMock()
            dummy_runner.is_running = False
            dummy_runner.condense_async = mock.AsyncMock()
            oh_app.conversation_runner = dummy_runner

            # Mock notify to ensure no error notifications
            notify_mock = mock.MagicMock()
            oh_app.notify = notify_mock

            oh_app.conversation_view.input_area._command_condense()

            # Verify the async method was called
            dummy_runner.condense_async.assert_called_once_with()
            # Verify no error notifications were sent
            notify_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_condense_command_no_runner_error_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/condense` should show error when no conversation runner exists."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Ensure no conversation runner
            oh_app.conversation_runner = None

            # Mock notify to capture the error message
            notify_mock = mock.MagicMock()
            oh_app.notify = notify_mock

            oh_app.conversation_view.input_area._command_condense()

            # Verify error notification was called with correct parameters
            notify_mock.assert_called_once_with(
                title="Condense Error",
                message="No conversation available to condense",
                severity="error",
            )

    @pytest.mark.asyncio
    async def test_feedback_command_opens_browser(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/feedback` should open the feedback form URL in the browser."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Mock webbrowser.open to verify it's called with correct URL
            with mock.patch("webbrowser.open") as mock_browser:
                # Mock notify to verify notification is shown
                notify_mock = mock.MagicMock()
                oh_app.notify = notify_mock

                oh_app.conversation_view.input_area._command_feedback()

                # Verify browser was opened with correct URL
                mock_browser.assert_called_once_with(
                    "https://forms.gle/chHc5VdS3wty5DwW6"
                )

                # Verify notification was shown
                notify_mock.assert_called_once_with(
                    title="Feedback",
                    message="Opening feedback form in your browser...",
                    severity="information",
                )

    @pytest.mark.asyncio
    async def test_new_command_starts_new_conversation(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/new` should start a new conversation with a new ID."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Store the original conversation ID
            original_conversation_id = oh_app.conversation_id

            # Mock notify to verify notification is shown
            notify_mock = mock.MagicMock()
            oh_app.notify = notify_mock

            # Call _command_new which posts NewConversationRequested message
            oh_app.conversation_view.input_area._command_new()

            # Process the message
            await pilot.pause()

            # Verify a new conversation ID was generated
            assert oh_app.conversation_id != original_conversation_id

            # Verify conversation runner was reset
            assert oh_app.conversation_runner is None

            # Verify notification was shown
            notify_mock.assert_called_once_with(
                title="New Conversation",
                message="Started a new conversation",
                severity="information",
            )

    @pytest.mark.asyncio
    async def test_new_command_blocked_when_conversation_running(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/new` should show warning when a conversation is running."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Set running state directly on ConversationView (source of truth)
            oh_app.conversation_view.running = True

            # Store the original conversation ID
            original_conversation_id = oh_app.conversation_id

            # Mock notify to verify warning is shown
            notify_mock = mock.MagicMock()
            oh_app.notify = notify_mock

            # Call _command_new which posts NewConversationRequested message
            oh_app.conversation_view.input_area._command_new()

            # Process the message
            await pilot.pause()

            # Verify conversation ID was NOT changed
            assert oh_app.conversation_id == original_conversation_id

            # Verify error notification was shown
            notify_mock.assert_called_once()
            call_args = notify_mock.call_args
            assert call_args[1]["title"] == "New Conversation Error"
            assert call_args[1]["severity"] == "error"

    @pytest.mark.asyncio
    async def test_new_command_clears_dynamically_added_widgets(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/new` should clear dynamically added widgets but keep splash widgets."""
        from textual.widgets import Static

        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Add a dynamic widget to scroll_view (simulating conversation content)
            dynamic_widget = Static("Test message", classes="user-message")
            oh_app.scroll_view.mount(dynamic_widget)
            await pilot.pause()

            # Verify the widget was added
            assert dynamic_widget in oh_app.scroll_view.children

            # Mock notify
            notify_mock = mock.MagicMock()
            oh_app.notify = notify_mock

            oh_app.conversation_view.input_area._command_new()
            await pilot.pause()

            # Verify dynamic widget was removed
            assert dynamic_widget not in oh_app.scroll_view.children

            # Verify splash widgets still exist
            splash_banner = oh_app.query_one("#splash_banner", Static)
            assert splash_banner is not None

    @pytest.mark.asyncio
    async def test_new_command_updates_splash_conversation_id(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/new` should update the splash conversation widget with new ID."""
        from textual.widgets import Static

        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Mock notify
            notify_mock = mock.MagicMock()
            oh_app.notify = notify_mock

            oh_app.conversation_view.input_area._command_new()
            await pilot.pause()

            # Verify splash conversation widget contains the new conversation ID
            splash_conversation = oh_app.query_one("#splash_conversation", Static)
            # The content should contain the new conversation ID hex
            # conversation_id is always set during app initialization
            assert oh_app.conversation_id is not None
            assert oh_app.conversation_id.hex in str(splash_conversation.content)

    @pytest.mark.asyncio
    async def test_history_command_toggles_panel(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/history` should toggle the history side panel visibility."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Initially panel should be hidden
            panels = oh_app.query(HistorySidePanel)
            initial_visible = (
                len(panels) > 0 and panels.first().display if len(panels) > 0 else False
            )

            oh_app.conversation_view.input_area._command_history()
            await pilot.pause()

            # Panel should now be visible
            panels = oh_app.query(HistorySidePanel)
            assert len(panels) > 0
            assert panels.first().display is True

            # Toggle again - should hide
            oh_app.conversation_view.input_area._command_history()
            await pilot.pause()

            panels = oh_app.query(HistorySidePanel)
            if len(panels) > 0:
                assert panels.first().display is False or initial_visible

    @pytest.mark.asyncio
    async def test_new_command_updates_history_panel(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/new` should add a placeholder to the history panel."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )
        existing_id = uuid.uuid4().hex
        monkeypatch.setattr(
            LocalFileStore,
            "list_conversations",
            lambda self, limit=100: [
                ConversationMetadata(
                    id=existing_id,
                    created_at=datetime(2025, 1, 1, tzinfo=UTC),
                    title="old chat",
                )
            ],
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)
            original_id = oh_app.conversation_id

            oh_app.conversation_view.input_area._command_history()
            await pilot.pause()

            panel = oh_app.query_one(HistorySidePanel)
            items_before = panel.query(HistoryItem)
            count_before = len(items_before)

            oh_app.conversation_view.input_area._command_new()
            await pilot.pause()

            assert oh_app.conversation_id != original_id

            items_after = panel.query(HistoryItem)
            assert len(items_after) == count_before + 1
            assert panel.current_conversation_id == oh_app.conversation_id

    @pytest.mark.asyncio
    async def test_history_panel_selection_triggers_switch(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Selecting a conversation in history panel should trigger switch."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )
        conv1_id = uuid.uuid4().hex
        conv2_id = uuid.uuid4().hex
        monkeypatch.setattr(
            LocalFileStore,
            "list_conversations",
            lambda self, limit=100: [
                ConversationMetadata(
                    id=conv1_id,
                    created_at=datetime(2025, 1, 2, tzinfo=UTC),
                    title="chat 1",
                ),
                ConversationMetadata(
                    id=conv2_id,
                    created_at=datetime(2025, 1, 1, tzinfo=UTC),
                    title="chat 2",
                ),
            ],
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            switch_calls: list[str] = []

            def mock_switch(cid: str) -> None:
                switch_calls.append(cid)

            oh_app._conversation_switcher.switch_to = mock_switch  # type: ignore[method-assign]

            oh_app.conversation_view.input_area._command_history()
            await pilot.pause()

            panel = oh_app.query_one(HistorySidePanel)
            panel._handle_select(conv2_id)
            await pilot.pause()

            assert len(switch_calls) == 1
            assert switch_calls[0] == conv2_id

    @pytest.mark.asyncio
    async def test_history_switch_shows_modal_when_agent_running(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Switching conversation while agent is running should show modal."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )
        target_id = uuid.uuid4().hex
        monkeypatch.setattr(
            LocalFileStore,
            "list_conversations",
            lambda self, limit=100: [
                ConversationMetadata(
                    id=target_id,
                    created_at=datetime(2025, 1, 1, tzinfo=UTC),
                    title="target chat",
                ),
            ],
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            dummy_runner = mock.MagicMock()
            dummy_runner.is_running = True
            oh_app.conversation_runner = dummy_runner

            oh_app._conversation_switcher.switch_to(target_id)
            await pilot.pause()

            top_screen = oh_app.screen_stack[-1]
            assert isinstance(top_screen, SwitchConversationModal)
