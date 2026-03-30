"""Tests for auto-copy on text selection functionality."""

from typing import cast
from unittest.mock import MagicMock, patch

import pyperclip
import pytest
from textual import events

from openhands_cli.tui.modals import SettingsScreen
from openhands_cli.tui.textual_app import OpenHandsApp


def _create_mouse_up_event() -> events.MouseUp:
    """Create a MouseUp event for testing."""
    return events.MouseUp(
        widget=None,
        x=0,
        y=0,
        delta_x=0,
        delta_y=0,
        button=0,
        shift=False,
        meta=False,
        ctrl=False,
    )


class TestAutoCopyOnSelection:
    """Tests for auto-copy on text selection in OpenHandsApp."""

    @pytest.mark.asyncio
    async def test_mouse_up_with_selection_copies_to_clipboard(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Mouse up with selected text copies to clipboard and shows notification."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        with patch("pyperclip.copy") as mock_copy:
            async with app.run_test() as pilot:
                oh_app = cast(OpenHandsApp, pilot.app)

                # Mock get_selected_text to return some text
                oh_app.screen.get_selected_text = MagicMock(
                    return_value="selected text"
                )

                # Mock notify to verify notification
                notify_mock = MagicMock()
                oh_app.notify = notify_mock

                # Simulate mouse up event
                oh_app.on_mouse_up(_create_mouse_up_event())

                # Verify pyperclip was called with selected text
                mock_copy.assert_called_once_with("selected text")

                # Verify notification was shown
                notify_mock.assert_called_once()
                call_args = notify_mock.call_args
                assert "Selection copied to clipboard" in call_args[0][0]
                assert call_args[1]["title"] == "Auto-copy"

    @pytest.mark.asyncio
    async def test_mouse_up_without_selection_does_nothing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Mouse up without selected text does not copy or notify."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        with patch("pyperclip.copy") as mock_copy:
            async with app.run_test() as pilot:
                oh_app = cast(OpenHandsApp, pilot.app)

                # Mock get_selected_text to return empty string
                oh_app.screen.get_selected_text = MagicMock(return_value="")

                # Mock notify
                notify_mock = MagicMock()
                oh_app.notify = notify_mock

                # Simulate mouse up event
                oh_app.on_mouse_up(_create_mouse_up_event())

                # Verify pyperclip was NOT called
                mock_copy.assert_not_called()

                # Verify notification was NOT shown
                notify_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_mouse_up_pyperclip_fails_on_linux_shows_xclip_hint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When pyperclip fails on Linux, notification includes xclip hint."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        with (
            patch(
                "pyperclip.copy",
                side_effect=pyperclip.PyperclipException("No clipboard"),
            ),
            patch.object(OpenHandsApp, "_is_linux", return_value=True),
        ):
            async with app.run_test() as pilot:
                oh_app = cast(OpenHandsApp, pilot.app)

                # Mock get_selected_text to return some text
                oh_app.screen.get_selected_text = MagicMock(
                    return_value="selected text"
                )

                # Mock notify to verify notification
                notify_mock = MagicMock()
                oh_app.notify = notify_mock

                # Mock copy_to_clipboard (OSC 52 fallback)
                oh_app.copy_to_clipboard = MagicMock()

                # Simulate mouse up event
                oh_app.on_mouse_up(_create_mouse_up_event())

                # Verify notification includes xclip hint
                notify_mock.assert_called_once()
                call_args = notify_mock.call_args
                assert "sudo apt install xclip" in call_args[0][0]
                assert call_args[1]["title"] == "Auto-copy"

    @pytest.mark.asyncio
    async def test_mouse_up_pyperclip_fails_on_non_linux_shows_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When pyperclip fails on non-Linux, shows success (OSC 52 likely works)."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        with (
            patch(
                "pyperclip.copy",
                side_effect=pyperclip.PyperclipException("No clipboard"),
            ),
            patch.object(OpenHandsApp, "_is_linux", return_value=False),
        ):
            async with app.run_test() as pilot:
                oh_app = cast(OpenHandsApp, pilot.app)

                # Mock get_selected_text to return some text
                oh_app.screen.get_selected_text = MagicMock(
                    return_value="selected text"
                )

                # Mock notify to verify notification
                notify_mock = MagicMock()
                oh_app.notify = notify_mock

                # Mock copy_to_clipboard (OSC 52 fallback)
                oh_app.copy_to_clipboard = MagicMock()

                # Simulate mouse up event
                oh_app.on_mouse_up(_create_mouse_up_event())

                # Verify notification shows success without xclip hint
                notify_mock.assert_called_once()
                call_args = notify_mock.call_args
                assert "Selection copied to clipboard" in call_args[0][0]
                assert "xclip" not in call_args[0][0]
                assert call_args[1]["title"] == "Auto-copy"

    @pytest.mark.asyncio
    async def test_mouse_up_get_selected_text_raises_does_not_crash(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """BUG-002: KeyError from Textual widget lifecycle during rapid clicking
        is caught and does not crash the application."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Mock get_selected_text to raise KeyError (Textual #5646)
            oh_app.screen.get_selected_text = MagicMock(
                side_effect=KeyError("toast--title")
            )

            # Mock notify to verify it is NOT called
            notify_mock = MagicMock()
            oh_app.notify = notify_mock

            # Simulate mouse up event — should not raise
            oh_app.on_mouse_up(_create_mouse_up_event())

            # Verify no notification (early return from except branch)
            notify_mock.assert_not_called()
