"""User settings storage for OpenHands CLI."""

import json
import os
import stat
from pathlib import Path


class UserSettingsError(Exception):
    """Exception raised for user settings storage errors."""

    pass


class UserSettings:
    """Local storage for user settings and profile information."""

    def __init__(self, config_dir: Path | None = None):
        """Initialize user settings storage.

        Args:
            config_dir: Directory to store settings (defaults to ~/.openhands)
        """
        if config_dir is None:
            config_dir = Path.home() / ".openhands"

        self.config_dir = config_dir
        self.config_dir.mkdir(mode=0o700, exist_ok=True)  # Secure permissions

        self.settings_file = self.config_dir / "user_settings.json"

        # Ensure secure permissions on config directory
        self._secure_directory()

    def _secure_directory(self) -> None:
        """Ensure the config directory has secure permissions."""
        try:
            # Set directory permissions to 700 (owner read/write/execute only)
            os.chmod(self.config_dir, stat.S_IRWXU)
        except OSError as e:
            raise UserSettingsError(f"Failed to secure config directory: {e}")



    def store_user_profile(self, server_url: str, profile_data: dict) -> None:
        """Store user profile data for a server.

        Args:
            server_url: The server URL this profile is for
            profile_data: Dictionary containing user profile information
        """
        try:
            # Load existing settings
            all_settings = {}
            if self.settings_file.exists():
                try:
                    with open(self.settings_file) as f:
                        all_settings = json.load(f)
                except (OSError, json.JSONDecodeError):
                    # If we can't read existing settings, start fresh
                    all_settings = {}

            # Add/update profile for this server
            all_settings[server_url] = profile_data

            # Save as plain JSON
            with open(self.settings_file, "w") as f:
                json.dump(all_settings, f, indent=2)

            # Secure permissions on settings file
            os.chmod(self.settings_file, stat.S_IRUSR | stat.S_IWUSR)  # 600

        except OSError as e:
            raise UserSettingsError(f"Failed to store user settings: {e}")

    def get_user_profile(self, server_url: str) -> dict | None:
        """Get stored user profile for a server.

        Args:
            server_url: The server URL to get profile for

        Returns:
            Dictionary containing user profile, or None if not found
        """
        if not self.settings_file.exists():
            return None

        try:
            with open(self.settings_file) as f:
                all_settings = json.load(f)
            return all_settings.get(server_url)

        except (OSError, json.JSONDecodeError):
            return None

    def remove_user_profile(self, server_url: str) -> bool:
        """Remove stored user profile for a server.

        Args:
            server_url: The server URL to remove profile for

        Returns:
            True if profile was removed, False if it didn't exist
        """
        if not self.settings_file.exists():
            return False

        try:
            with open(self.settings_file) as f:
                all_settings = json.load(f)

            if server_url not in all_settings:
                return False

            del all_settings[server_url]

            # Save updated settings
            if all_settings:
                with open(self.settings_file, "w") as f:
                    json.dump(all_settings, f, indent=2)
            else:
                # No settings left, remove the file
                self.settings_file.unlink()

            return True

        except (OSError, json.JSONDecodeError):
            return False

    def clear_all_profiles(self) -> None:
        """Remove all stored user profiles."""
        try:
            if self.settings_file.exists():
                self.settings_file.unlink()
        except OSError as e:
            raise UserSettingsError(f"Failed to clear user settings: {e}")

    def list_servers(self) -> list[str]:
        """List all servers with stored user profiles.

        Returns:
            List of server URLs with stored profiles
        """
        if not self.settings_file.exists():
            return []

        try:
            with open(self.settings_file) as f:
                all_settings = json.load(f)
            return list(all_settings.keys())

        except (OSError, json.JSONDecodeError):
            return []

    def get_setting(self, server_url: str, setting_name: str, default=None):
        """Get a specific setting value for a server.

        Args:
            server_url: The server URL
            setting_name: Name of the setting to retrieve
            default: Default value if setting not found

        Returns:
            Setting value or default
        """
        profile = self.get_user_profile(server_url)
        if not profile:
            return default

        settings = profile.get("settings", {})
        return settings.get(setting_name, default)

    def get_user_info(self, server_url: str) -> dict | None:
        """Get basic user information for a server.

        Args:
            server_url: The server URL

        Returns:
            Dictionary with user_id, email, username or None
        """
        profile = self.get_user_profile(server_url)
        if not profile:
            return None

        return {
            "user_id": profile.get("user_id"),
            "email": profile.get("email"),
            "username": profile.get("username"),
        }

    def get_api_keys(self, server_url: str) -> list[dict]:
        """Get API keys information for a server.

        Args:
            server_url: The server URL

        Returns:
            List of API key information (without actual key values)
        """
        profile = self.get_user_profile(server_url)
        if not profile:
            return []

        return profile.get("api_keys", [])


# Global user settings instance
_user_settings: UserSettings | None = None


def get_user_settings() -> UserSettings:
    """Get the global user settings instance."""
    global _user_settings
    if _user_settings is None:
        _user_settings = UserSettings()
    return _user_settings
