"""Storage module for plugin marketplace configurations.

This module handles persistence of marketplaces to ~/.openhands/marketplaces.json
"""

import json
import os
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from openhands_cli.locations import MARKETPLACES_FILE, PERSISTENCE_DIR

# Directory for caching marketplace indexes
MARKETPLACE_CACHE_DIR = os.path.join(PERSISTENCE_DIR, "marketplace_cache")


class MarketplaceError(Exception):
    """Exception raised for marketplace-related errors."""

    pass


@dataclass
class MarketplaceSource:
    """Represents a marketplace source configuration."""

    source_type: str  # "github", "git", "url"
    repo: str | None = None  # For github: "owner/repo"
    url: str | None = None  # For git/url types

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {"source": self.source_type}
        if self.repo:
            result["repo"] = self.repo
        if self.url:
            result["url"] = self.url
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MarketplaceSource":
        """Create from dictionary."""
        return cls(
            source_type=data.get("source", "url"),
            repo=data.get("repo"),
            url=data.get("url"),
        )

    def __str__(self) -> str:
        """Return string representation."""
        if self.source_type == "github" and self.repo:
            return f"github:{self.repo}"
        elif self.url:
            return self.url
        return f"{self.source_type}:{self.repo or self.url}"

    def get_fetch_url(self) -> str:
        """Get the URL to fetch the marketplace index from.

        Returns:
            URL string for fetching the marketplace index.

        Raises:
            MarketplaceError: If the source type doesn't support fetching.
        """
        if self.source_type == "url" and self.url:
            return self.url
        elif self.source_type == "github" and self.repo:
            # Fetch from GitHub raw content (assumes marketplace.json at repo root)
            return f"https://raw.githubusercontent.com/{self.repo}/main/marketplace.json"
        elif self.source_type == "git" and self.url:
            raise MarketplaceError(
                f"Git repositories require cloning. Use GitHub or direct URL instead."
            )
        else:
            raise MarketplaceError(f"Cannot fetch from source: {self}")


@dataclass
class Marketplace:
    """Represents a plugin marketplace configuration."""

    name: str
    source: MarketplaceSource
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str | None = None
    auto_update: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source": self.source.to_dict(),
            "added_at": self.added_at,
            "last_updated": self.last_updated,
            "auto_update": self.auto_update,
        }

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "Marketplace":
        """Create from dictionary."""
        return cls(
            name=name,
            source=MarketplaceSource.from_dict(data.get("source", {})),
            added_at=data.get("added_at", datetime.now().isoformat()),
            last_updated=data.get("last_updated"),
            auto_update=data.get("auto_update", True),
        )


def parse_source(source_str: str) -> tuple[str, MarketplaceSource]:
    """Parse a source string into a name and MarketplaceSource.

    Supported formats:
    - owner/repo -> github shorthand
    - github:owner/repo -> explicit github
    - https://gitlab.com/org/plugins.git -> git URL
    - https://example.com/marketplace.json -> direct URL

    Args:
        source_str: The source string to parse.

    Returns:
        Tuple of (generated_name, MarketplaceSource)
    """
    # GitHub explicit: github:owner/repo
    if source_str.startswith("github:"):
        repo = source_str[7:]  # Remove "github:" prefix
        name = repo.replace("/", "-")
        return name, MarketplaceSource(source_type="github", repo=repo)

    # Git URL: ends with .git
    if source_str.endswith(".git"):
        # Extract name from URL
        match = re.search(r"/([^/]+)\.git$", source_str)
        name = match.group(1) if match else "unknown"
        return name, MarketplaceSource(source_type="git", url=source_str)

    # Direct URL: starts with http:// or https://
    if source_str.startswith("http://") or source_str.startswith("https://"):
        # Extract name from URL path
        match = re.search(r"/([^/]+?)(?:\.json)?$", source_str)
        name = match.group(1) if match else "unknown"
        return name, MarketplaceSource(source_type="url", url=source_str)

    # GitHub shorthand: owner/repo (no protocol, contains single /)
    if "/" in source_str and not source_str.startswith("/"):
        parts = source_str.split("/")
        if len(parts) == 2:
            name = source_str.replace("/", "-")
            return name, MarketplaceSource(source_type="github", repo=source_str)

    # Fallback: treat as URL
    return source_str, MarketplaceSource(source_type="url", url=source_str)


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
            return {"marketplaces": {}}

        try:
            with open(self.config_path, encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {"marketplaces": {}}
                data = json.loads(content)
                # Ensure marketplaces key exists
                if "marketplaces" not in data:
                    data["marketplaces"] = {}
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
        marketplaces_dict = config.get("marketplaces", {})
        return [
            Marketplace.from_dict(name, data)
            for name, data in marketplaces_dict.items()
        ]

    def add_marketplace(
        self, source_str: str, name: str | None = None
    ) -> Marketplace:
        """Add a new marketplace.

        Args:
            source_str: Source string (GitHub shorthand, Git URL, or direct URL).
            name: Optional custom name for the marketplace.

        Returns:
            The created Marketplace object.

        Raises:
            MarketplaceError: If the marketplace already exists.
        """
        config = self._load_config()
        marketplaces = config.get("marketplaces", {})

        # Parse source string
        generated_name, source = parse_source(source_str)
        marketplace_name = name or generated_name

        # Check if marketplace already exists
        if marketplace_name in marketplaces:
            raise MarketplaceError(f"Marketplace already exists: {marketplace_name}")

        # Create new marketplace
        marketplace = Marketplace(name=marketplace_name, source=source)
        marketplaces[marketplace_name] = marketplace.to_dict()
        config["marketplaces"] = marketplaces

        self._save_config(config)
        return marketplace

    def remove_marketplace(self, name: str) -> None:
        """Remove a marketplace by name.

        Args:
            name: Name of the marketplace to remove.

        Raises:
            MarketplaceError: If the marketplace is not found.
        """
        config = self._load_config()
        marketplaces = config.get("marketplaces", {})

        if name not in marketplaces:
            raise MarketplaceError(f"Marketplace not found: {name}")

        del marketplaces[name]
        config["marketplaces"] = marketplaces
        self._save_config(config)

    def get_marketplace(self, name: str) -> Marketplace | None:
        """Get a marketplace by name.

        Args:
            name: Name of the marketplace.

        Returns:
            Marketplace object if found, None otherwise.
        """
        config = self._load_config()
        marketplaces = config.get("marketplaces", {})

        if name in marketplaces:
            return Marketplace.from_dict(name, marketplaces[name])
        return None

    def update_marketplace(self, name: str) -> dict[str, Any]:
        """Fetch and update the marketplace index.

        Re-fetches the marketplace index from the source and updates
        the cached copy and metadata.

        Args:
            name: Name of the marketplace to update.

        Returns:
            The fetched marketplace index data.

        Raises:
            MarketplaceError: If the marketplace is not found or fetch fails.
        """
        config = self._load_config()
        marketplaces = config.get("marketplaces", {})

        if name not in marketplaces:
            raise MarketplaceError(f"Marketplace not found: {name}")

        marketplace = Marketplace.from_dict(name, marketplaces[name])

        # Fetch the marketplace index
        index_data = self._fetch_marketplace_index(marketplace)

        # Cache the fetched index
        self._cache_marketplace_index(name, index_data)

        # Update the last_updated timestamp
        marketplaces[name]["last_updated"] = datetime.now().isoformat()
        config["marketplaces"] = marketplaces
        self._save_config(config)

        return index_data

    def _fetch_marketplace_index(self, marketplace: Marketplace) -> dict[str, Any]:
        """Fetch the marketplace index from the source.

        Args:
            marketplace: The marketplace to fetch the index for.

        Returns:
            The parsed marketplace index data.

        Raises:
            MarketplaceError: If the fetch fails.
        """
        try:
            fetch_url = marketplace.source.get_fetch_url()
        except MarketplaceError:
            raise

        try:
            request = urllib.request.Request(
                fetch_url,
                headers={"User-Agent": "OpenHands-CLI/1.0"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read().decode("utf-8")
                return json.loads(content)
        except urllib.error.HTTPError as e:
            raise MarketplaceError(
                f"Failed to fetch marketplace index: HTTP {e.code} - {e.reason}"
            )
        except urllib.error.URLError as e:
            raise MarketplaceError(f"Failed to connect to marketplace: {e.reason}")
        except json.JSONDecodeError as e:
            raise MarketplaceError(f"Invalid JSON in marketplace index: {e}")
        except TimeoutError:
            raise MarketplaceError("Timeout while fetching marketplace index")

    def _cache_marketplace_index(self, name: str, index_data: dict[str, Any]) -> None:
        """Cache the marketplace index to disk.

        Args:
            name: Name of the marketplace.
            index_data: The marketplace index data to cache.
        """
        os.makedirs(MARKETPLACE_CACHE_DIR, exist_ok=True)
        cache_path = os.path.join(MARKETPLACE_CACHE_DIR, f"{name}.json")
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2)
        except OSError as e:
            raise MarketplaceError(f"Failed to cache marketplace index: {e}")

    def get_cached_index(self, name: str) -> dict[str, Any] | None:
        """Get the cached marketplace index.

        Args:
            name: Name of the marketplace.

        Returns:
            The cached index data, or None if not cached.
        """
        cache_path = os.path.join(MARKETPLACE_CACHE_DIR, f"{name}.json")
        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
