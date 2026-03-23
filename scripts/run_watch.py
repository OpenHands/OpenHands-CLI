#!/usr/bin/env python3
"""Watch for file changes and restart openhands CLI with proper terminal handling.

This script manages the subprocess lifecycle properly, ensuring clean terminal
state between restarts. It watches openhands_cli/ for .py and .tcss file changes.

Note: Terminal reset (stty) is Unix-only. On Windows, basic ANSI reset is used.
"""

import signal
import subprocess
import sys
import time
from pathlib import Path


# Configuration constants
DEBOUNCE_MS = 1000  # Wait 1s after last change before restarting
POLL_INTERVAL_MS = 100  # Check for changes every 100ms
TERMINAL_SETTLE_DELAY = 0.2  # Wait 200ms for terminal cleanup
PROCESS_SHUTDOWN_TIMEOUT = 3  # Wait 3s for graceful shutdown


def reset_terminal():
    """Reset terminal to a clean state."""
    # ANSI escape sequences to reset terminal
    sys.stdout.write("\033[?1049l")  # Exit alternate screen buffer
    sys.stdout.write("\033[0m")  # Reset colors/attributes
    sys.stdout.write("\033[?25h")  # Show cursor
    sys.stdout.write("\033[H\033[2J")  # Clear screen and move to top
    sys.stdout.flush()

    # Unix-only: reset terminal line settings
    if sys.platform != "win32":
        import os

        os.system("stty sane 2>/dev/null")


def print_status(msg: str):
    """Print a status message."""
    print(f"\033[33m[watch]\033[0m {msg}")


def is_watched_file(path: str) -> bool:
    """Check if file should trigger a restart."""
    return path.endswith(".py") or path.endswith(".tcss")


class WatchRunner:
    """Manages the app subprocess lifecycle during watch mode."""

    def __init__(self):
        self.process: subprocess.Popen | None = None

    def start_app(self):
        """Start the openhands app in a subprocess."""
        reset_terminal()
        print_status("Starting openhands...")
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "openhands_cli.entrypoint",
                "--exit-without-confirmation",
            ],
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    def stop_app(self):
        """Stop the running app gracefully."""
        if self.process and self.process.poll() is None:
            print_status("Stopping app...")
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=PROCESS_SHUTDOWN_TIMEOUT)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            reset_terminal()
        self.process = None

    def check_if_exited(self):
        """Check if app exited on its own and report status."""
        if self.process and self.process.poll() is not None:
            exit_code = self.process.returncode
            if exit_code != 0:
                print_status(f"App crashed with exit code {exit_code}")
            else:
                print_status("App exited. Waiting for changes to restart...")
            self.process = None

    def run(self):
        """Main watch loop."""
        from watchfiles import watch

        watch_path = Path("openhands_cli")
        if not watch_path.exists():
            print_status(f"Error: {watch_path} not found. Run from repo root.")
            sys.exit(1)

        def signal_handler(_signum, _frame):
            """Handle Ctrl+C to exit cleanly."""
            self.stop_app()
            reset_terminal()
            print_status("Stopped watching.")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start initial app
        self.start_app()

        print_status(f"Watching {watch_path}/ for changes (Ctrl+C to stop)")

        # Watch for changes
        for changes in watch(
            watch_path,
            watch_filter=lambda _change, path: is_watched_file(path),
            debounce=DEBOUNCE_MS,
            step=POLL_INTERVAL_MS,
        ):
            self.check_if_exited()

            changed_files = [Path(p).name for _, p in list(changes)[:3]]
            if len(changes) > 3:
                changed_files.append(f"... and {len(changes) - 3} more")

            print_status(f"Changed: {', '.join(changed_files)}")

            # Restart app
            self.stop_app()
            time.sleep(TERMINAL_SETTLE_DELAY)
            self.start_app()


if __name__ == "__main__":
    runner = WatchRunner()
    runner.run()
