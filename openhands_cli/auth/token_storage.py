"""Simple API key storage for OpenHands CLI authentication."""

import os
from pathlib import Path

from openhands_cli.locations import PERSISTENCE_DIR


class TokenStorageError(Exception):
    """Exception raised for token storage errors."""

    pass


class TokenStorage:
    """Simple local storage for API keys."""

    def __init__(self, config_dir: Path | None = None):
        """Initialize token storage.

        Args:
            config_dir: Directory to store API keys (defaults to PERSISTENCE_DIR)
        """
        if config_dir is None:
            config_dir = Path(PERSISTENCE_DIR)

        self.config_dir = config_dir
        self.config_dir.mkdir(mode=0o700, exist_ok=True)  # Secure permissions

        self.api_key_file = self.config_dir / "api_key.txt"

    def store_api_key(self, api_key: str) -> None:
        """Store API key as plain text.

        Args:
            api_key: The API key to store
        """
        try:
            with open(self.api_key_file, "w") as f:
                f.write(api_key)

            # Set secure permissions on API key file (owner read/write only)
            os.chmod(self.api_key_file, 0o600)

        except OSError as e:
            raise TokenStorageError(f"Failed to store API key: {e}")

    def get_api_key(self) -> str | None:
        """Get stored API key.

        Returns:
            The stored API key, or None if not found
        """
        if not self.api_key_file.exists():
            return None

        try:
            with open(self.api_key_file) as f:
                return f.read().strip()
        except OSError:
            return None

    def remove_api_key(self) -> bool:
        """Remove stored API key.

        Returns:
            True if API key was removed, False if it didn't exist
        """
        if not self.api_key_file.exists():
            return False

        try:
            self.api_key_file.unlink()
            return True
        except OSError:
            return False

    def has_api_key(self) -> bool:
        """Check if an API key is stored.

        Returns:
            True if an API key is stored, False otherwise
        """
        return self.api_key_file.exists() and self.get_api_key() is not None

    # Legacy methods for backward compatibility
    def store_tokens(self, server_url: str, tokens: dict) -> None:  # noqa: ARG002
        """Store tokens (legacy method - stores the access_token as API key)."""
        if "access_token" in tokens:
            self.store_api_key(tokens["access_token"])

    def get_tokens(self, server_url: str) -> dict | None:  # noqa: ARG002
        """Get tokens (legacy method - returns API key as access_token)."""
        api_key = self.get_api_key()
        if api_key:
            return {"access_token": api_key, "token_type": "Bearer"}
        return None

    def remove_tokens(self, server_url: str) -> bool:  # noqa: ARG002
        """Remove tokens (legacy method)."""
        return self.remove_api_key()

    def clear_all_tokens(self) -> None:
        """Remove all stored tokens (legacy method)."""
        self.remove_api_key()

    def list_servers(self) -> list[str]:
        """List servers with stored tokens (legacy method)."""
        return [] if not self.has_api_key() else ["default"]


# Global token storage instance
_token_storage: TokenStorage | None = None


def get_token_storage() -> TokenStorage:
    """Get the global token storage instance."""
    global _token_storage
    if _token_storage is None:
        _token_storage = TokenStorage()
    return _token_storage
