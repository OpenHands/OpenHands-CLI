#!/usr/bin/env python3
"""Helper script for running openhands with watchfiles and proper terminal handling.

This script ensures the terminal state is properly restored between restarts,
which can be an issue when watchfiles sends SIGINT to stop the TUI.
"""

import os
import signal
import subprocess
import sys


def reset_terminal():
    """Reset terminal to a sane state."""
    # Use stty sane to reset terminal settings
    try:
        subprocess.run(["stty", "sane"], check=False, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass
    # Also try tput reset for good measure (clears screen state)
    try:
        subprocess.run(["tput", "reset"], check=False, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass


def run_openhands():
    """Run openhands CLI with proper signal handling."""
    # Set up signal handler to reset terminal on exit
    def signal_handler(signum, frame):
        reset_terminal()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Import and run the app
        from openhands_cli.tui.textual_app import main as textual_main

        textual_main(exit_without_confirmation=True)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        reset_terminal()


if __name__ == "__main__":
    run_openhands()
