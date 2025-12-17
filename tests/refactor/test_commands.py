"""Tests for the commands module."""

from typing import cast
from unittest import mock

import pytest
from textual.containers import VerticalScroll
from textual_autocomplete import DropdownItem

from openhands.sdk.security.confirmation_policy import AlwaysConfirm
from openhands_cli.refactor.core.commands import COMMANDS, is_valid_command, show_help
from openhands_cli.refactor.modals import SettingsScreen
from openhands_cli.refactor.modals.confirmation_modal import (
    ConfirmationSettingsModal,
)
from openhands_cli.refactor.modals.exit_modal import ExitConfirmationModal
from openhands_cli.refactor.textual_app import OpenHandsApp


class TestCommands:
    """Tests for command definitions and handlers."""

    def test_commands_list_structure(self):
        """Test that COMMANDS list has correct structure."""
        assert isinstance(COMMANDS, list)
        assert len(COMMANDS) == 4

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
            ("/confirm", "Configure confirmation settings"),
            ("/condense", "Condense conversation history"),
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
        assert params[0] == "main_display"

    @pytest.mark.parametrize(
        "expected_content",
        [
            "OpenHands CLI Help",
            "/help",
            "/confirm",
            "/condense",
            "/exit",
            "Display available commands",
            "Configure confirmation settings",
            "Condense conversation history",
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
            ("/confirm", True),
            ("/condense", True),
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


class TestOpenHandsAppCommands:
    """Integration-style tests for command handling in OpenHandsApp."""

    @pytest.mark.asyncio
    async def test_confirm_command_opens_confirmation_settings_modal(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda: False,
        )

        app = OpenHandsApp(exit_confirmation=True)

        dummy_runner = mock.MagicMock()
        dummy_runner.get_confirmation_policy.return_value = AlwaysConfirm()
        app.conversation_runner = dummy_runner

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            oh_app._handle_command("/confirm")

            top_screen = oh_app.screen_stack[-1]
            assert isinstance(top_screen, ConfirmationSettingsModal)
            dummy_runner.get_confirmation_policy.assert_called_once()

    @pytest.mark.asyncio
    async def test_exit_command_opens_exit_confirmation_modal_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`/exit` should open ExitConfirmationModal when exit_confirmation is True."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda: False,
        )

        app = OpenHandsApp(exit_confirmation=True)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            oh_app._handle_command("/exit")

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
            lambda: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Replace exit with a MagicMock so we can assert it was called
            exit_mock = mock.MagicMock()
            oh_app.exit = exit_mock

            oh_app._handle_command("/exit")

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
            lambda: False,
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

            oh_app._handle_command("/condense")

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
            lambda: False,
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

            oh_app._handle_command("/condense")

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
            lambda: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Ensure no conversation runner
            oh_app.conversation_runner = None

            # Mock notify to capture the error message
            notify_mock = mock.MagicMock()
            oh_app.notify = notify_mock

            oh_app._handle_command("/condense")

            # Verify error notification was called with correct parameters
            notify_mock.assert_called_once_with(
                title="Condense Error",
                message="No conversation available to condense",
                severity="error",
            )
