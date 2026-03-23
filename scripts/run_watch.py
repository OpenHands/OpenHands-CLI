#!/usr/bin/env python3
"""Watch for file changes and restart openhands CLI with proper terminal handling.

This script manages the subprocess lifecycle properly, ensuring clean terminal
state between restarts. It watches openhands_cli/ for .py and .tcss file changes.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def reset_terminal():
    """Reset terminal to a completely clean state."""
    # ANSI escape sequences to fully reset terminal
    sys.stdout.write("\033[?1049l")  # Exit alternate screen buffer
    sys.stdout.write("\033[0m")  # Reset colors/attributes
    sys.stdout.write("\033[?25h")  # Show cursor
    sys.stdout.write("\033[H\033[2J")  # Clear screen and move to top
    sys.stdout.flush()
    os.system("stty sane 2>/dev/null")


def print_status(msg: str):
    """Print a status message."""
    print(f"\033[33m[watch]\033[0m {msg}")


def run_watch():
    """Main watch loop using watchfiles."""
    from watchfiles import watch

    watch_path = Path("openhands_cli")
    if not watch_path.exists():
        print_status(f"Error: {watch_path} not found. Run from repo root.")
        sys.exit(1)

    process: subprocess.Popen | None = None

    def start_app():
        """Start the openhands app in a subprocess."""
        nonlocal process
        reset_terminal()
        print_status("Starting openhands...")
        process = subprocess.Popen(
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

    def stop_app():
        """Stop the running app gracefully."""
        nonlocal process
        if process and process.poll() is None:
            print_status("Stopping app...")
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            reset_terminal()
        process = None

    def signal_handler(_signum, _frame):
        """Handle Ctrl+C to exit cleanly."""
        stop_app()
        reset_terminal()
        print_status("Stopped watching.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start initial app
    start_app()

    print_status(f"Watching {watch_path}/ for changes (Ctrl+C to stop)")

    def is_watched_file(path: str) -> bool:
        """Check if file should trigger a restart."""
        return path.endswith(".py") or path.endswith(".tcss")

    # Watch for changes
    for changes in watch(
        watch_path,
        watch_filter=lambda _change, path: is_watched_file(path),
        debounce=1000,  # 1 second debounce
        step=100,
    ):
        # Check if process exited on its own (user quit)
        if process and process.poll() is not None:
            print_status("App exited. Waiting for changes to restart...")
            process = None

        # Filter to watched files (double-check)
        relevant_changes = [(c, p) for c, p in changes if is_watched_file(p)]
        if not relevant_changes:
            continue

        changed_files = [Path(p).name for _, p in relevant_changes[:3]]
        if len(relevant_changes) > 3:
            changed_files.append(f"... and {len(relevant_changes) - 3} more")

        print_status(f"Changed: {', '.join(changed_files)}")

        # Restart app
        stop_app()
        time.sleep(0.2)  # Small delay for terminal to settle
        start_app()


if __name__ == "__main__":
    run_watch()
