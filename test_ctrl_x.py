#!/usr/bin/env python3
"""
Quick test script to verify CTRL+X external editor functionality.
This script creates a minimal app to test the key binding.
"""

import os
import tempfile
from textual.app import App, ComposeResult
from textual.widgets import Static

from openhands_cli.tui.widgets.input_field import InputField


class TestApp(App):
    """Minimal test app for CTRL+X functionality."""

    def compose(self) -> ComposeResult:
        yield Static("Test CTRL+X External Editor Functionality", id="header")
        yield Static("Press CTRL+X to test external editor", id="instructions")
        yield InputField()

    def on_mount(self) -> None:
        """Set up test environment."""
        # Set a simple editor for testing
        os.environ["EDITOR"] = "echo 'Test content from editor' >"


if __name__ == "__main__":
    print("Testing CTRL+X external editor functionality...")
    print("1. The app should show 'Ctrl+X for custom editor' in the status line")
    print("2. Press CTRL+X to test the external editor")
    print("3. Press CTRL+Q to quit")
    print()
    
    app = TestApp()
    app.run()