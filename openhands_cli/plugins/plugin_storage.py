"""Storage module for installed plugin configurations.

This module handles persistence of installed plugins to ~/.openhands/plugins.json
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from openhands_cli.locations import INSTALLED_PLUGINS_FILE, PERSISTENCE_DIR


class PluginStorageError(Exception):
    """Exception raised for plugin storage-related errors."""

    pass


@dataclass
class InstalledPlugin:
    """Represents an installed plugin configuration."""

    name: str
    marketplace: str
    enabled: bool = True
    version: str | None = None
    installed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved_ref: str | None = None
    source_url: str | None = None

    @property
    def full_name(self) -> str:
        """Get the fully qualified plugin name (name@marketplace)."""
        return f"{self.name}@{self.marketplace}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "marketplace": self.marketplace,
            "enabled": self.enabled,
            "version": self.version,
            "installed_at": self.installed_at,
            "resolved_ref": self.resolved_ref,
            "source_url": self.source_url,
        }

    @classmethod
    def from_dict(cls, key: str, data: dict[str, Any]) -> "InstalledPlugin":
        """Create from dictionary.

        Args:
            key: The plugin key (name@marketplace format)
            data: Plugin data dictionary
        """
        # Parse name and marketplace from key if not in data
        if "@" in key:
            name, marketplace = key.rsplit("@", 1)
        else:
            name = data.get("name", key)
            marketplace = data.get("marketplace", "unknown")

        return cls(
            name=data.get("name", name),
            marketplace=data.get("marketplace", marketplace),
            enabled=data.get("enabled", True),
            version=data.get("version"),
            installed_at=data.get("installed_at", datetime.now().isoformat()),
            resolved_ref=data.get("resolved_ref"),
            source_url=data.get("source_url"),
        )


class PluginStorage:
    """Handles storage and retrieval of installed plugin configurations."""

    def __init__(self, config_path: str | None = None):
        """Initialize plugin storage.

        Args:
            config_path: Optional path to config file. Defaults to INSTALLED_PLUGINS_FILE.
        """
        self.config_path = config_path or INSTALLED_PLUGINS_FILE

    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists."""
        os.makedirs(PERSISTENCE_DIR, exist_ok=True)

    def _load_config(self) -> dict[str, Any]:
        """Load the plugin configuration from file.

        Returns:
            Dictionary containing plugin configurations.
        """
        if not os.path.exists(self.config_path):
            return {"installed": {}}

        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = json.load(f)
                # Ensure installed key exists
                if "installed" not in data:
                    data["installed"] = {}
                return data
        except json.JSONDecodeError as e:
            raise PluginStorageError(f"Invalid JSON in config file: {e}")
        except OSError as e:
            raise PluginStorageError(f"Failed to read config file: {e}")

    def _save_config(self, config: dict[str, Any]) -> None:
        """Save the plugin configuration to file.

        Args:
            config: Configuration dictionary to save.
        """
        self._ensure_config_dir()
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except OSError as e:
            raise PluginStorageError(f"Failed to save config file: {e}")

    def list_plugins(
        self, enabled_only: bool = False, disabled_only: bool = False
    ) -> list[InstalledPlugin]:
        """List all installed plugins.

        Args:
            enabled_only: If True, only return enabled plugins.
            disabled_only: If True, only return disabled plugins.

        Returns:
            List of InstalledPlugin objects.
        """
        config = self._load_config()
        plugins = []

        for key, data in config.get("installed", {}).items():
            plugin = InstalledPlugin.from_dict(key, data)

            if enabled_only and not plugin.enabled:
                continue
            if disabled_only and plugin.enabled:
                continue

            plugins.append(plugin)

        return plugins

    def get_enabled_plugins(self) -> list[InstalledPlugin]:
        """Get all enabled plugins.

        Returns:
            List of enabled InstalledPlugin objects.
        """
        return self.list_plugins(enabled_only=True)

    def install_plugin(
        self,
        name: str,
        marketplace: str,
        version: str | None = None,
        source_url: str | None = None,
        resolved_ref: str | None = None,
    ) -> InstalledPlugin:
        """Install a new plugin.

        Args:
            name: Plugin name.
            marketplace: Marketplace name.
            version: Optional plugin version.
            source_url: Optional source URL for the plugin.
            resolved_ref: Optional resolved git ref.

        Returns:
            The created InstalledPlugin object.

        Raises:
            PluginStorageError: If the plugin is already installed.
        """
        config = self._load_config()
        installed = config.get("installed", {})

        full_name = f"{name}@{marketplace}"

        # Check if plugin already exists
        if full_name in installed:
            raise PluginStorageError(f"Plugin already installed: {full_name}")

        # Create new plugin
        plugin = InstalledPlugin(
            name=name,
            marketplace=marketplace,
            version=version,
            source_url=source_url,
            resolved_ref=resolved_ref,
        )
        installed[full_name] = plugin.to_dict()
        config["installed"] = installed

        self._save_config(config)
        return plugin

    def uninstall_plugin(self, full_name: str) -> None:
        """Uninstall a plugin.

        Args:
            full_name: Full plugin name (name@marketplace).

        Raises:
            PluginStorageError: If the plugin is not found.
        """
        config = self._load_config()
        installed = config.get("installed", {})

        if full_name not in installed:
            raise PluginStorageError(f"Plugin not found: {full_name}")

        del installed[full_name]
        config["installed"] = installed
        self._save_config(config)

    def get_plugin(self, full_name: str) -> InstalledPlugin | None:
        """Get a plugin by full name.

        Args:
            full_name: Full plugin name (name@marketplace).

        Returns:
            InstalledPlugin object if found, None otherwise.
        """
        config = self._load_config()
        installed = config.get("installed", {})

        if full_name in installed:
            return InstalledPlugin.from_dict(full_name, installed[full_name])
        return None

    def find_plugin_by_name(self, name: str) -> list[InstalledPlugin]:
        """Find plugins by name (without marketplace).

        Args:
            name: Plugin name.

        Returns:
            List of matching InstalledPlugin objects.
        """
        plugins = self.list_plugins()
        return [p for p in plugins if p.name == name]

    def enable_plugin(self, full_name: str) -> None:
        """Enable a plugin.

        Args:
            full_name: Full plugin name (name@marketplace).

        Raises:
            PluginStorageError: If the plugin is not found.
        """
        config = self._load_config()
        installed = config.get("installed", {})

        if full_name not in installed:
            raise PluginStorageError(f"Plugin not found: {full_name}")

        installed[full_name]["enabled"] = True
        config["installed"] = installed
        self._save_config(config)

    def disable_plugin(self, full_name: str) -> None:
        """Disable a plugin.

        Args:
            full_name: Full plugin name (name@marketplace).

        Raises:
            PluginStorageError: If the plugin is not found.
        """
        config = self._load_config()
        installed = config.get("installed", {})

        if full_name not in installed:
            raise PluginStorageError(f"Plugin not found: {full_name}")

        installed[full_name]["enabled"] = False
        config["installed"] = installed
        self._save_config(config)

    def resolve_plugin_name(self, name: str) -> str:
        """Resolve a plugin name to full name.

        If the name contains @, it's already a full name.
        If not, try to find a unique match.

        Args:
            name: Plugin name (with or without marketplace).

        Returns:
            Full plugin name.

        Raises:
            PluginStorageError: If name is ambiguous or not found.
        """
        if "@" in name:
            return name

        matches = self.find_plugin_by_name(name)
        if not matches:
            raise PluginStorageError(f"Plugin not found: {name}")
        if len(matches) > 1:
            marketplaces = ", ".join(p.marketplace for p in matches)
            raise PluginStorageError(
                f"Ambiguous plugin name '{name}'. "
                f"Found in marketplaces: {marketplaces}. "
                f"Please specify as '{name}@<marketplace>'."
            )
        return matches[0].full_name
