"""E2E snapshot tests for the CloudLoginScreen.

These tests verify the visual appearance of the cloud login flow
with mocked API calls to avoid actual network requests.
"""

from typing import TYPE_CHECKING, Any

from .helpers import wait_for_app_ready


if TYPE_CHECKING:
    from textual.pilot import Pilot


def _create_cloud_login_test_app(auto_start_login: bool = True):
    """Create a test app that shows CloudLoginScreen directly.

    Args:
        auto_start_login: If False, don't auto-start the login worker
    """
    from textual.app import App, ComposeResult
    from textual.widgets import Footer, Static

    from openhands_cli.theme import OPENHANDS_THEME
    from openhands_cli.tui.modals.cloud_login_screen import CloudLoginScreen

    class TestCloudLoginScreen(CloudLoginScreen):
        """CloudLoginScreen configured via class attribute."""

        pass

    # Set the class attribute based on the parameter
    TestCloudLoginScreen.auto_start_login = auto_start_login

    class CloudLoginTestApp(App[None]):
        """Test app for CloudLoginScreen snapshots."""

        CSS = """
        Screen {
            background: $background;
        }

        #main_content {
            width: 100%;
            height: 100%;
            content-align: center middle;
        }
        """

        login_screen: TestCloudLoginScreen

        def __init__(self, **kwargs: Any):
            super().__init__(**kwargs)
            self.register_theme(OPENHANDS_THEME)
            self.theme = OPENHANDS_THEME.name

        def compose(self) -> ComposeResult:
            yield Static("Background content", id="main_content")
            yield Footer()

        def on_mount(self) -> None:
            self.login_screen = TestCloudLoginScreen(
                on_login_success=lambda: None,
                on_login_cancelled=lambda: None,
            )
            self.push_screen(self.login_screen)

    return CloudLoginTestApp()


# =============================================================================
# Test: Cloud Login Screen States
# =============================================================================


class TestCloudLoginScreenSnapshots:
    """Snapshot tests for CloudLoginScreen."""

    def test_initial_loading_state(self, snap_compare):
        """Test the initial loading state of the cloud login screen."""
        app = _create_cloud_login_test_app(auto_start_login=False)
        assert snap_compare(app, terminal_size=(120, 40), run_before=wait_for_app_ready)

    def test_verification_url_displayed(self, snap_compare):
        """Test the screen when verification URL is displayed."""

        async def setup(pilot: "Pilot"):
            await wait_for_app_ready(pilot)

            # Get the CloudLoginScreen from the app (use getattr for type safety)
            screen = getattr(pilot.app, "login_screen")
            screen._update_status("Browser opened. Complete login in your browser.")
            screen._show_verification_url(
                "https://app.all-hands.dev/oauth/device?code=ABCD1234",
                "ABCD-1234",
            )
            await wait_for_app_ready(pilot)

        app = _create_cloud_login_test_app(auto_start_login=False)
        assert snap_compare(app, terminal_size=(120, 40), run_before=setup)

    def test_waiting_for_auth_state(self, snap_compare):
        """Test the screen when waiting for authentication."""

        async def setup(pilot: "Pilot"):
            await wait_for_app_ready(pilot)

            screen = getattr(pilot.app, "login_screen")
            screen._update_status("Browser opened. Complete login in your browser.")
            screen._show_verification_url(
                "https://app.all-hands.dev/oauth/device?code=WXYZ5678",
                "WXYZ-5678",
            )
            screen._update_instructions("Waiting for authentication to complete...")
            await wait_for_app_ready(pilot)

        app = _create_cloud_login_test_app(auto_start_login=False)
        assert snap_compare(app, terminal_size=(120, 40), run_before=setup)

    def test_success_state(self, snap_compare):
        """Test the screen when login is successful."""

        async def setup(pilot: "Pilot"):
            await wait_for_app_ready(pilot)

            screen = getattr(pilot.app, "login_screen")
            screen._update_status("✓ Logged into OpenHands Cloud!")
            screen._show_verification_url(
                "https://app.all-hands.dev/oauth/device?code=SUCCESS",
                "SUCC-ESS1",
            )
            screen._update_instructions("✓ Settings synchronized!")
            await wait_for_app_ready(pilot)

        app = _create_cloud_login_test_app(auto_start_login=False)
        assert snap_compare(app, terminal_size=(120, 40), run_before=setup)

    def test_error_state(self, snap_compare):
        """Test the screen when login fails."""

        async def setup(pilot: "Pilot"):
            await wait_for_app_ready(pilot)

            screen = getattr(pilot.app, "login_screen")
            screen._update_status("Authentication failed: Device code expired")
            screen._update_instructions("Please try again or cancel.")
            await wait_for_app_ready(pilot)

        app = _create_cloud_login_test_app(auto_start_login=False)
        assert snap_compare(app, terminal_size=(120, 40), run_before=setup)
