"""CLI settings models and utilities."""

import json
import os
from pathlib import Path

from pydantic import BaseModel


# Default threshold for iterative refinement (60% - same as SDK default)
DEFAULT_CRITIC_THRESHOLD = 0.6

# Default maximum number of refinement iterations per user turn
DEFAULT_MAX_REFINEMENT_ITERATIONS = 3


class CriticSettings(BaseModel):
    """Model for critic-related settings."""

    enable_critic: bool = True
    enable_iterative_refinement: bool = False
    critic_threshold: float = DEFAULT_CRITIC_THRESHOLD
    max_refinement_iterations: int = DEFAULT_MAX_REFINEMENT_ITERATIONS


class CliSettings(BaseModel):
    """Model for CLI-level settings."""

    default_cells_expanded: bool = False
    auto_open_plan_panel: bool = True
    critic: CriticSettings = CriticSettings()

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the path to the CLI configuration file."""
        # Use environment variable if set, otherwise use default
        persistence_dir = os.environ.get(
            "PERSISTENCE_DIR", os.path.expanduser("~/.openhands")
        )
        return Path(persistence_dir) / "cli_config.json"

    @classmethod
    def _migrate_legacy_settings(cls, data: dict) -> dict:
        """Migrate legacy flat settings format to new nested format.

        Old format (pre-nested):
            {"enable_critic": true, "default_cells_expanded": false}

        New format (nested CriticSettings):
            {"critic": {"enable_critic": true}, "default_cells_expanded": false}

        Args:
            data: Raw settings data from disk

        Returns:
            Migrated settings data compatible with current schema
        """
        # Check if migration is needed (old format has enable_critic at top level)
        if "enable_critic" in data and "critic" not in data:
            # Extract critic-related fields from top level
            critic_data = {}
            fields_to_migrate = [
                "enable_critic",
                "enable_iterative_refinement",
                "critic_threshold",
                "max_refinement_iterations",
            ]

            for field in fields_to_migrate:
                if field in data:
                    critic_data[field] = data.pop(field)

            # Create nested critic structure
            if critic_data:
                data["critic"] = critic_data

        return data

    @classmethod
    def load(cls) -> "CliSettings":
        """Load CLI settings from file.

        Automatically migrates legacy flat settings format to the new nested
        CriticSettings structure. If migration occurs, the file is re-saved
        in the new format.

        Returns:
            CliSettings instance with loaded settings, or defaults if file doesn't
            exist
        """
        config_path = cls.get_config_path()

        if not config_path.exists():
            return cls()

        try:
            with open(config_path) as f:
                data = json.load(f)

            # Check if migration is needed
            needs_migration = "enable_critic" in data and "critic" not in data

            # Migrate legacy format if needed
            data = cls._migrate_legacy_settings(data)

            settings = cls.model_validate(data)

            # Re-save migrated settings to update file format
            if needs_migration:
                settings.save()

            return settings
        except (json.JSONDecodeError, ValueError):
            # If file is corrupted, return defaults
            return cls()

    def save(self) -> None:
        """Save CLI settings to file."""
        config_path = self.get_config_path()

        # Ensure the persistence directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)
