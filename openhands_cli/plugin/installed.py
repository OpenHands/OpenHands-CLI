"""Installed plugins management for OpenHands CLI.

This module provides utilities for managing plugins installed in the user's
home directory (~/.openhands/plugins/installed/).

Note: This is a local implementation while waiting for SDK PR #2031 to be merged.
Once the SDK includes these utilities, this module can be refactored to use them.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from openhands.sdk.plugin.fetch import (
    PluginFetchError,
    fetch_plugin_with_resolution,
)
from openhands.sdk.plugin.plugin import Plugin


# Default directory for installed plugins
DEFAULT_INSTALLED_PLUGINS_DIR = Path.home() / ".openhands" / "plugins" / "installed"

# Metadata file for tracking installed plugins
_METADATA_FILENAME = ".installed.json"

_PLUGIN_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _resolve_installed_dir(installed_dir: Path | None) -> Path:
    """Return installed_dir or the default if None."""
    return installed_dir if installed_dir is not None else DEFAULT_INSTALLED_PLUGINS_DIR


def get_installed_plugins_dir() -> Path:
    """Get the default directory for installed plugins.

    Returns:
        Path to ~/.openhands/plugins/installed/
    """
    return DEFAULT_INSTALLED_PLUGINS_DIR


def _validate_plugin_name(name: str) -> None:
    """Validate plugin name is Claude-like kebab-case.

    This protects filesystem operations (install/uninstall) from path traversal.
    """
    if not _PLUGIN_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            f"Invalid plugin name. Expected kebab-case like 'my-plugin' (got {name!r})."
        )


class InstalledPluginInfo(BaseModel):
    """Information about an installed plugin."""

    name: str = Field(description="Plugin name (from manifest)")
    version: str = Field(default="1.0.0", description="Plugin version")
    description: str = Field(default="", description="Plugin description")
    source: str = Field(description="Original source (e.g., 'github:owner/repo')")
    resolved_ref: str | None = Field(
        default=None,
        description="Resolved git commit SHA (for version pinning)",
    )
    repo_path: str | None = Field(
        default=None,
        description="Subdirectory path within the repository (for monorepos)",
    )
    installed_at: str = Field(
        description="ISO 8601 timestamp of installation",
    )
    install_path: str = Field(
        description="Path where the plugin is installed",
    )

    @classmethod
    def from_plugin(
        cls,
        plugin: Plugin,
        source: str,
        resolved_ref: str | None,
        repo_path: str | None,
        install_path: Path,
    ) -> InstalledPluginInfo:
        """Create InstalledPluginInfo from a loaded Plugin."""
        return cls(
            name=plugin.name,
            version=plugin.version,
            description=plugin.description,
            source=source,
            resolved_ref=resolved_ref,
            repo_path=repo_path,
            installed_at=datetime.now(UTC).isoformat(),
            install_path=str(install_path),
        )


class InstalledPluginsMetadata(BaseModel):
    """Metadata file for tracking all installed plugins."""

    plugins: dict[str, InstalledPluginInfo] = Field(
        default_factory=dict,
        description="Map of plugin name to installation info",
    )

    @classmethod
    def get_path(cls, installed_dir: Path) -> Path:
        """Get the metadata file path for the given installed plugins directory."""
        return installed_dir / _METADATA_FILENAME

    @classmethod
    def load_from_dir(cls, installed_dir: Path) -> InstalledPluginsMetadata:
        """Load metadata from the installed plugins directory."""
        metadata_path = cls.get_path(installed_dir)
        if not metadata_path.exists():
            return cls()
        try:
            with open(metadata_path) as f:
                data = json.load(f)
            return cls.model_validate(data)
        except Exception:
            return cls()

    def save_to_dir(self, installed_dir: Path) -> None:
        """Save metadata to the installed plugins directory."""
        metadata_path = self.get_path(installed_dir)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)


def install_plugin(
    source: str,
    ref: str | None = None,
    repo_path: str | None = None,
    installed_dir: Path | None = None,
    force: bool = False,
) -> InstalledPluginInfo:
    """Install a plugin from a source.

    Args:
        source: Plugin source - can be:
            - "github:owner/repo" - GitHub shorthand
            - Any git URL
            - Local path
        ref: Optional branch, tag, or commit to install.
        repo_path: Subdirectory path within the repository (for monorepos).
        installed_dir: Directory for installed plugins.
        force: If True, overwrite existing installation.

    Returns:
        InstalledPluginInfo with details about the installation.

    Raises:
        PluginFetchError: If fetching the plugin fails.
        FileExistsError: If plugin is already installed and force=False.
    """
    installed_dir = _resolve_installed_dir(installed_dir)

    # Fetch the plugin
    fetched_path, resolved_ref = fetch_plugin_with_resolution(
        source=source,
        ref=ref,
        repo_path=repo_path,
        update=True,
    )

    # Load the plugin to get its metadata
    plugin = Plugin.load(fetched_path)
    plugin_name = plugin.name
    _validate_plugin_name(plugin_name)

    # Check if already installed
    install_path = installed_dir / plugin_name
    if install_path.exists() and not force:
        raise FileExistsError(
            f"Plugin '{plugin_name}' is already installed at {install_path}. "
            f"Use force=True to overwrite."
        )

    # Remove existing installation if force=True
    if install_path.exists():
        shutil.rmtree(install_path)

    # Copy plugin to installed directory
    installed_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(fetched_path, install_path)

    # Create installation info
    info = InstalledPluginInfo.from_plugin(
        plugin=plugin,
        source=source,
        resolved_ref=resolved_ref,
        repo_path=repo_path,
        install_path=install_path,
    )

    # Update metadata
    metadata = InstalledPluginsMetadata.load_from_dir(installed_dir)
    metadata.plugins[plugin_name] = info
    metadata.save_to_dir(installed_dir)

    return info


def uninstall_plugin(
    name: str,
    installed_dir: Path | None = None,
) -> bool:
    """Uninstall a plugin by name.

    Args:
        name: Name of the plugin to uninstall.
        installed_dir: Directory for installed plugins.

    Returns:
        True if the plugin was uninstalled, False if it wasn't installed.
    """
    _validate_plugin_name(name)
    installed_dir = _resolve_installed_dir(installed_dir)

    metadata = InstalledPluginsMetadata.load_from_dir(installed_dir)
    if name not in metadata.plugins:
        return False

    plugin_path = installed_dir / name
    if plugin_path.exists():
        shutil.rmtree(plugin_path)

    del metadata.plugins[name]
    metadata.save_to_dir(installed_dir)

    return True


def _validate_tracked_plugins(
    metadata: InstalledPluginsMetadata, installed_dir: Path
) -> tuple[list[InstalledPluginInfo], bool]:
    """Validate tracked plugins exist on disk."""
    valid_plugins: list[InstalledPluginInfo] = []
    changed = False

    for name, info in list(metadata.plugins.items()):
        try:
            _validate_plugin_name(name)
        except ValueError:
            del metadata.plugins[name]
            changed = True
            continue

        plugin_path = installed_dir / name
        if plugin_path.exists():
            valid_plugins.append(info)
        else:
            del metadata.plugins[name]
            changed = True

    return valid_plugins, changed


def _discover_untracked_plugins(
    metadata: InstalledPluginsMetadata, installed_dir: Path
) -> tuple[list[InstalledPluginInfo], bool]:
    """Discover plugin directories not tracked in metadata."""
    discovered: list[InstalledPluginInfo] = []
    changed = False

    for item in installed_dir.iterdir():
        if not item.is_dir() or item.name.startswith("."):
            continue
        if item.name in metadata.plugins:
            continue

        try:
            _validate_plugin_name(item.name)
        except ValueError:
            continue

        try:
            plugin = Plugin.load(item)
        except Exception:
            continue

        if plugin.name != item.name:
            continue

        info = InstalledPluginInfo(
            name=plugin.name,
            version=plugin.version,
            description=plugin.description,
            source="local",
            installed_at=datetime.now(UTC).isoformat(),
            install_path=str(item),
        )
        discovered.append(info)
        metadata.plugins[item.name] = info
        changed = True

    return discovered, changed


def list_installed_plugins(
    installed_dir: Path | None = None,
) -> list[InstalledPluginInfo]:
    """List all installed plugins.

    Args:
        installed_dir: Directory for installed plugins.

    Returns:
        List of InstalledPluginInfo for each installed plugin.
    """
    installed_dir = _resolve_installed_dir(installed_dir)

    if not installed_dir.exists():
        return []

    metadata = InstalledPluginsMetadata.load_from_dir(installed_dir)

    # Validate tracked plugins and discover untracked ones
    valid_plugins, tracked_changed = _validate_tracked_plugins(metadata, installed_dir)
    discovered, discovered_changed = _discover_untracked_plugins(
        metadata, installed_dir
    )

    if tracked_changed or discovered_changed:
        metadata.save_to_dir(installed_dir)

    return valid_plugins + discovered


def get_installed_plugin(
    name: str,
    installed_dir: Path | None = None,
) -> InstalledPluginInfo | None:
    """Get information about a specific installed plugin.

    Args:
        name: Name of the plugin to look up.
        installed_dir: Directory for installed plugins.

    Returns:
        InstalledPluginInfo if the plugin is installed, None otherwise.
    """
    _validate_plugin_name(name)
    installed_dir = _resolve_installed_dir(installed_dir)

    metadata = InstalledPluginsMetadata.load_from_dir(installed_dir)
    info = metadata.plugins.get(name)

    # Verify the plugin directory still exists
    if info is not None:
        plugin_path = installed_dir / name
        if not plugin_path.exists():
            return None

    return info


def update_plugin(
    name: str,
    installed_dir: Path | None = None,
) -> InstalledPluginInfo | None:
    """Update an installed plugin to the latest version.

    Args:
        name: Name of the plugin to update.
        installed_dir: Directory for installed plugins.

    Returns:
        Updated InstalledPluginInfo if successful, None if plugin not installed.

    Raises:
        PluginFetchError: If fetching the updated plugin fails.
    """
    _validate_plugin_name(name)
    installed_dir = _resolve_installed_dir(installed_dir)

    # Get current installation info
    current_info = get_installed_plugin(name, installed_dir)
    if current_info is None:
        return None

    # Re-install from the original source
    return install_plugin(
        source=current_info.source,
        ref=None,  # Get latest
        repo_path=current_info.repo_path,
        installed_dir=installed_dir,
        force=True,
    )


# Re-export PluginFetchError for convenience
__all__ = [
    "InstalledPluginInfo",
    "InstalledPluginsMetadata",
    "PluginFetchError",
    "get_installed_plugin",
    "get_installed_plugins_dir",
    "install_plugin",
    "list_installed_plugins",
    "uninstall_plugin",
    "update_plugin",
]
