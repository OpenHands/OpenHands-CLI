import os
import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def force_color_session():
    """Force Textual to think it's running in a TTY with color support."""
    # We can't use monkeypatch in session scope easily without some hacks,
    # or we just modify sys/os directly and revert (or not, since it's a test session).

    old_stdout_isatty = getattr(sys.stdout, "isatty", None)
    old_stderr_isatty = getattr(sys.stderr, "isatty", None)
    old_stdin_isatty = getattr(sys.stdin, "isatty", None)

    # Patch
    sys.stdout.isatty = lambda: True
    sys.stderr.isatty = lambda: True
    sys.stdin.isatty = lambda: True

    # Env vars
    os.environ["TERM"] = "xterm-256color"
    os.environ["FORCE_COLOR"] = "1"
    os.environ["CLICOLOR_FORCE"] = "1"
    if "NO_COLOR" in os.environ:
        del os.environ["NO_COLOR"]

    yield

    # Revert (optional but good practice)
    if old_stdout_isatty:
        sys.stdout.isatty = old_stdout_isatty
    if old_stderr_isatty:
        sys.stderr.isatty = old_stderr_isatty
    if old_stdin_isatty:
        sys.stdin.isatty = old_stdin_isatty
