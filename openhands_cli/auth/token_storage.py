"""Simple API key storage for OpenHands CLI authentication."""

import os
from pathlib import Path

from openhands_cli.locations import PERSISTENCE_DIR


class TokenStorage:
    """Simple local storage for API keys."""

    def __init__(self, config_dir: Path | None = None):
        """Initialize token storage.

        Args:
            config_dir: Directory to store API keys (defaults to PERSISTENCE_DIR/cloud)
        """
        if config_dir is None:
            config_dir = Path(PERSISTENCE_DIR) / "cloud"

        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.api_key_file = self.config_dir / "api_key.txt"

    def store_api_key(self, api_key: str) -> None:
        """Store API key as plain text with secure permissions.

        Args:
            api_key: The API key to store
        """
        with open(self.api_key_file, "w") as f:
            f.write(api_key)

        # Set secure permissions (read/write for owner only)
        os.chmod(self.api_key_file, 0o600)

    def get_api_key(self) -> str | None:
        """Get stored API key.

        Returns:
            The stored API key, or None if not found
        """
        if not self.api_key_file.exists():
            return None

        with open(self.api_key_file) as f:
            return f.read().strip()

    def remove_api_key(self) -> bool:
        """Remove stored API key.

        Returns:
            True if API key was removed, False if it didn't exist
        """
        if not self.api_key_file.exists():
            return False

        self.api_key_file.unlink()
        return True

    def has_api_key(self) -> bool:
        """Check if an API key is stored.

        Returns:
            True if an API key is stored, False otherwise
        """
        return self.api_key_file.exists() and self.get_api_key() is not None
