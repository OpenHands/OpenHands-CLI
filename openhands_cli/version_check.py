"""Version checking utilities for OpenHands CLI."""

import json
import urllib.request
from typing import NamedTuple

from openhands_cli import __version__


class VersionInfo(NamedTuple):
    """Version information for display."""

    current_version: str
    latest_version: str | None
    needs_update: bool
    error: str | None


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers for comparison.

    Args:
        version_str: Version string like "1.2.1"

    Returns:
        Tuple of integers like (1, 2, 1)
    """
    return tuple(int(x) for x in version_str.split("."))


def check_for_updates(timeout: float = 2.0) -> VersionInfo:
    """Check if a newer version is available on PyPI.

    Args:
        timeout: Timeout for PyPI request in seconds

    Returns:
        VersionInfo with update information
    """
    current = __version__

    # Handle dev versions or special cases
    if current == "0.0.0" or "dev" in current:
        return VersionInfo(
            current_version=current,
            latest_version=None,
            needs_update=False,
            error=None,
        )

    try:
        # Fetch latest version from PyPI
        url = "https://pypi.org/pypi/openhands/json"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", f"openhands-cli/{current}")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            latest = data["info"]["version"]

        # Compare versions
        try:
            current_tuple = parse_version(current)
            latest_tuple = parse_version(latest)
            needs_update = latest_tuple > current_tuple
        except (ValueError, AttributeError):
            # If we can't parse versions, assume no update needed
            needs_update = False

        return VersionInfo(
            current_version=current,
            latest_version=latest,
            needs_update=needs_update,
            error=None,
        )
    except Exception as e:
        # Don't block on network errors - just return current version
        return VersionInfo(
            current_version=current,
            latest_version=None,
            needs_update=False,
            error=str(e),
        )
