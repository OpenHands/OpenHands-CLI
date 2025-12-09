"""Tests for --exit-without-confirmation CLI parameter functionality."""

import sys
from unittest.mock import patch

import pytest

from openhands_cli.simple_main import main


@pytest.mark.asyncio
async def test_exit_without_confirmation_shows_modal_via_args():
    """Test that without --exit-without-confirmation, Ctrl+Q shows confirmation modal via CLI args."""
    argv = ["openhands", "--exp"]
    captured_app = None
    
    def capture_app_and_run_test(self):
        """Capture the app instance and run with pilot for testing."""
        nonlocal captured_app
        captured_app = self
        return self.run_test()
    
    # Patch sys.argv to simulate CLI invocation
    with patch.object(sys, 'argv', argv):
        from openhands_cli.refactor.textual_app import OpenHandsApp
        
        with patch.object(OpenHandsApp, 'run', capture_app_and_run_test):
            # This will create the app via argument parsing and capture it
            main()
            
            # Now test the captured app
            assert captured_app is not None, "App should have been captured"
            
            async with captured_app.run_test() as pilot:
                # Press Ctrl+Q to trigger exit
                await pilot.press("ctrl+q")
                
                # Should show the exit confirmation modal
                from openhands_cli.refactor.modals.exit_modal import ExitConfirmationModal
                
                # The modal should be pushed as a screen
                modal_screens = [screen for screen in captured_app.screen_stack if isinstance(screen, ExitConfirmationModal)]
                assert len(modal_screens) == 1, "Exit confirmation modal should be shown when --exit-without-confirmation is not used"


@pytest.mark.asyncio
async def test_exit_without_confirmation_exits_immediately_via_args():
    """Test that with --exit-without-confirmation, Ctrl+Q exits immediately without modal via CLI args."""
    argv = ["openhands", "--exp", "--exit-without-confirmation"]
    captured_app = None
    
    def capture_app_and_run_test(self):
        """Capture the app instance and run with pilot for testing."""
        nonlocal captured_app
        captured_app = self
        return self.run_test()
    
    # Patch sys.argv to simulate CLI invocation
    with patch.object(sys, 'argv', argv):
        from openhands_cli.refactor.textual_app import OpenHandsApp
        
        with patch.object(OpenHandsApp, 'run', capture_app_and_run_test):
            # This will create the app via argument parsing and capture it
            main()
            
            # Now test the captured app
            assert captured_app is not None, "App should have been captured"
            
            async with captured_app.run_test() as pilot:
                # Press Ctrl+Q to trigger exit
                await pilot.press("ctrl+q")
                
                # App should exit immediately without showing modal
                from openhands_cli.refactor.modals.exit_modal import ExitConfirmationModal
                
                modal_screens = [screen for screen in captured_app.screen_stack if isinstance(screen, ExitConfirmationModal)]
                assert len(modal_screens) == 0, "No exit confirmation modal should be shown when --exit-without-confirmation is used"