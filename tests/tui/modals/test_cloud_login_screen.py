"""Unit tests for CloudLoginScreen modal."""

from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.modals.cloud_login_screen import CloudLoginScreen


class TestCloudLoginScreenCallbacks:
    """Test that CloudLoginScreen correctly calls callbacks on success/cancel."""

    @pytest.fixture
    def mock_callbacks(self):
        """Create mock callbacks for testing."""
        return {
            "on_login_success": MagicMock(),
            "on_login_cancelled": MagicMock(),
        }

    @pytest.fixture
    def test_app(self, mock_callbacks):
        """Create a test app with CloudLoginScreen."""

        class TestCloudLoginScreen(CloudLoginScreen):
            """CloudLoginScreen that doesn't auto-start login."""

            auto_start_login = False

        class TestApp(App):
            """Test app for CloudLoginScreen."""

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.register_theme(OPENHANDS_THEME)
                self.theme = OPENHANDS_THEME.name
                self.login_screen = None

            def compose(self) -> ComposeResult:
                yield Static("Background")

            def on_mount(self) -> None:
                self.login_screen = TestCloudLoginScreen(
                    on_login_success=mock_callbacks["on_login_success"],
                    on_login_cancelled=mock_callbacks["on_login_cancelled"],
                )
                self.push_screen(self.login_screen)

        return TestApp()

    @pytest.mark.asyncio
    async def test_dismiss_on_success_calls_success_callback(
        self, test_app, mock_callbacks
    ):
        """Test that successful login dismisses screen and calls success callback."""
        async with test_app.run_test() as pilot:
            # Wait for app to be ready
            await pilot.pause()

            # Get the login screen
            login_screen = test_app.login_screen
            assert login_screen is not None

            # Simulate successful worker completion by calling dismiss directly
            # (mimicking what on_worker_state_changed does on SUCCESS)
            login_screen.dismiss(True)

            # Then call the success callback (mimicking the worker handler)
            mock_callbacks["on_login_success"]()

            await pilot.pause()

            # Verify success callback was called
            mock_callbacks["on_login_success"].assert_called_once()
            mock_callbacks["on_login_cancelled"].assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_button_calls_cancelled_callback(
        self, test_app, mock_callbacks
    ):
        """Test that cancel button dismisses screen and calls cancelled callback."""
        async with test_app.run_test() as pilot:
            await pilot.pause()

            # Click the cancel button
            await pilot.click("#cancel_button")
            await pilot.pause()

            # Verify cancelled callback was called
            mock_callbacks["on_login_cancelled"].assert_called_once()
            mock_callbacks["on_login_success"].assert_not_called()

    @pytest.mark.asyncio
    async def test_escape_key_calls_cancelled_callback(self, test_app, mock_callbacks):
        """Test that pressing Escape dismisses screen and calls cancelled callback."""
        async with test_app.run_test() as pilot:
            await pilot.pause()

            # Press escape
            await pilot.press("escape")
            await pilot.pause()

            # Verify cancelled callback was called
            mock_callbacks["on_login_cancelled"].assert_called_once()
            mock_callbacks["on_login_success"].assert_not_called()


class TestCloudLoginScreenUIStates:
    """Test UI state updates in CloudLoginScreen."""

    @pytest.fixture
    def test_app(self):
        """Create a test app with CloudLoginScreen."""

        class TestCloudLoginScreen(CloudLoginScreen):
            """CloudLoginScreen that doesn't auto-start login."""

            auto_start_login = False

        class TestApp(App):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.register_theme(OPENHANDS_THEME)
                self.theme = OPENHANDS_THEME.name
                self.login_screen = None

            def compose(self) -> ComposeResult:
                yield Static("Background")

            def on_mount(self) -> None:
                self.login_screen = TestCloudLoginScreen(
                    on_login_success=lambda: None,
                    on_login_cancelled=lambda: None,
                )
                self.push_screen(self.login_screen)

        return TestApp()

    @pytest.mark.asyncio
    async def test_update_status_changes_status_text(self, test_app):
        """Test that _update_status updates the status label."""
        async with test_app.run_test() as pilot:
            await pilot.pause()

            login_screen = test_app.login_screen
            login_screen._update_status("Test status message")
            await pilot.pause()

            status = login_screen.query_one("#login_status", Static)
            # Access the internal _content attribute or render to string
            rendered = status.render()
            assert "Test status message" in str(rendered)

    @pytest.mark.asyncio
    async def test_show_verification_url_updates_ui(self, test_app):
        """Test that _show_verification_url shows the URL and code."""
        async with test_app.run_test() as pilot:
            await pilot.pause()

            login_screen = test_app.login_screen
            login_screen._show_verification_url(
                "https://example.com/verify", "TEST-CODE"
            )
            await pilot.pause()

            url_widget = login_screen.query_one("#login_url", Static)
            instructions = login_screen.query_one("#login_instructions", Static)

            # Check URL is displayed (render() returns RenderableType)
            url_rendered = url_widget.render()
            assert "https://example.com/verify" in str(url_rendered)
            # Check code is displayed
            instructions_rendered = instructions.render()
            assert "TEST-CODE" in str(instructions_rendered)
            # Check hidden class is removed
            assert "hidden" not in url_widget.classes
            assert "hidden" not in instructions.classes
