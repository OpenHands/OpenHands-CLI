"""Storage module for plugin marketplace configurations.

This module handles persistence of marketplace URLs to ~/.openhands/marketplaces.json
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from openhands_cli.locations import MARKETPLACES_FILE, PERSISTENCE_DIR


class MarketplaceError(Exception):
    """Exception raised for marketplace-related errors."""

    pass


@dataclass
class Marketplace:
    """Represents a plugin marketplace configuration."""

    url: str
    name: str | None = None
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "url": self.url,
            "name": self.name,
            "added_at": self.added_at,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Marketplace":
        """Create from dictionary."""
        return cls(
            url=data["url"],
            name=data.get("name"),
            added_at=data.get("added_at", datetime.now().isoformat()),
            last_updated=data.get("last_updated"),
        )


class MarketplaceStorage:
    """Handles storage and retrieval of marketplace configurations."""

    def __init__(self, config_path: str | None = None):
        """Initialize marketplace storage.

        Args:
            config_path: Optional path to config file. Defaults to MARKETPLACES_FILE.
        """
        self.config_path = config_path or MARKETPLACES_FILE

    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists."""
        os.makedirs(PERSISTENCE_DIR, exist_ok=True)

    def _load_config(self) -> dict[str, Any]:
        """Load the marketplace configuration from file.

        Returns:
            Dictionary containing marketplace configurations.
        """
        if not os.path.exists(self.config_path):
            return {"marketplaces": []}

        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = json.load(f)
                # Ensure marketplaces key exists
                if "marketplaces" not in data:
                    data["marketplaces"] = []
                return data
        except json.JSONDecodeError as e:
            raise MarketplaceError(f"Invalid JSON in config file: {e}")
        except OSError as e:
            raise MarketplaceError(f"Failed to read config file: {e}")

    def _save_config(self, config: dict[str, Any]) -> None:
        """Save the marketplace configuration to file.

        Args:
            config: Configuration dictionary to save.
        """
        self._ensure_config_dir()
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except OSError as e:
            raise MarketplaceError(f"Failed to save config file: {e}")

    def list_marketplaces(self) -> list[Marketplace]:
        """List all configured marketplaces.

        Returns:
            List of Marketplace objects.
        """
        config = self._load_config()
        return [Marketplace.from_dict(m) for m in config.get("marketplaces", [])]

    def add_marketplace(self, url: str, name: str | None = None) -> Marketplace:
        """Add a new marketplace.

        Args:
            url: URL of the marketplace.
            name: Optional friendly name for the marketplace.

        Returns:
            The created Marketplace object.

        Raises:
            MarketplaceError: If the marketplace already exists.
        """
        config = self._load_config()
        marketplaces = config.get("marketplaces", [])

        # Check if marketplace already exists
        for m in marketplaces:
            if m["url"] == url:
                raise MarketplaceError(f"Marketplace already exists: {url}")

        # Create new marketplace
        marketplace = Marketplace(url=url, name=name)
        marketplaces.append(marketplace.to_dict())
        config["marketplaces"] = marketplaces

        self._save_config(config)
        return marketplace

    def remove_marketplace(self, url: str) -> None:
        """Remove a marketplace by URL.

        Args:
            url: URL of the marketplace to remove.

        Raises:
            MarketplaceError: If the marketplace is not found.
        """
        config = self._load_config()
        marketplaces = config.get("marketplaces", [])

        # Find and remove the marketplace
        original_count = len(marketplaces)
        marketplaces = [m for m in marketplaces if m["url"] != url]

        if len(marketplaces) == original_count:
            raise MarketplaceError(f"Marketplace not found: {url}")

        config["marketplaces"] = marketplaces
        self._save_config(config)

    def get_marketplace(self, url: str) -> Marketplace | None:
        """Get a marketplace by URL.

        Args:
            url: URL of the marketplace.

        Returns:
            Marketplace object if found, None otherwise.
        """
        config = self._load_config()
        for m in config.get("marketplaces", []):
            if m["url"] == url:
                return Marketplace.from_dict(m)
        return None

    def update_marketplace_timestamp(self, url: str) -> None:
        """Update the last_updated timestamp for a marketplace.

        Args:
            url: URL of the marketplace to update.

        Raises:
            MarketplaceError: If the marketplace is not found.
        """
        config = self._load_config()
        marketplaces = config.get("marketplaces", [])

        found = False
        for m in marketplaces:
            if m["url"] == url:
                m["last_updated"] = datetime.now().isoformat()
                found = True
                break

        if not found:
            raise MarketplaceError(f"Marketplace not found: {url}")

        config["marketplaces"] = marketplaces
        self._save_config(config)
