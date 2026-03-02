"""CLI settings models and utilities."""

import json
import os
from pathlib import Path

from pydantic import BaseModel, field_validator


# Default marketplace path placeholder - shown in UI as a suggestion
# When marketplace_path is None, all public skills are loaded without filtering
DEFAULT_MARKETPLACE_PATH = "marketplaces/default.json"

# Refinement triggers when predicted success probability falls below this threshold
# Default: 0.6 (60%) - agent is prompted to review work when critic scores < 60%
DEFAULT_CRITIC_THRESHOLD = 0.6

# Individual issue detection threshold - refinement triggers when any specific
# issue (e.g., insufficient_testing) has probability >= this value
# Default: 0.75 (75%) - even if overall score is good
DEFAULT_ISSUE_THRESHOLD = 0.75

# Default maximum number of refinement iterations per user turn
DEFAULT_MAX_REFINEMENT_ITERATIONS = 3


class CriticSettings(BaseModel):
    """Model for critic-related settings."""

    enable_critic: bool = True
    enable_iterative_refinement: bool = False
    critic_threshold: float = DEFAULT_CRITIC_THRESHOLD
    issue_threshold: float = DEFAULT_ISSUE_THRESHOLD
    max_refinement_iterations: int = DEFAULT_MAX_REFINEMENT_ITERATIONS

    @field_validator("critic_threshold", "issue_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate that threshold is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator("max_refinement_iterations")
    @classmethod
    def validate_max_iterations(cls, v: int) -> int:
        """Validate that max iterations is between 1 and 10."""
        if not 1 <= v <= 10:
            raise ValueError(f"Max iterations must be between 1 and 10, got {v}")
        return v


class CliSettings(BaseModel):
    """Model for CLI-level settings."""

    default_cells_expanded: bool = False
    auto_open_plan_panel: bool = True
    # None = load all public skills, path string = filter to specific marketplace
    marketplace_path: str | None = None
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
    def _migrate_legacy_settings(cls, data: dict) -> tuple[dict, bool]:
        """Migrate legacy settings format to current format.

        Handles migration from old format where `enable_critic` was at the top level
        to new format where critic settings are nested under `critic`.

        Args:
            data: Raw settings data from config file

        Returns:
            Tuple of (migrated settings data, bool indicating if migration occurred)
        """
        migrated = False

        # Check for legacy top-level enable_critic (pre-nested format)
        if "enable_critic" in data and "critic" not in data:
            # Migrate enable_critic to nested critic.enable_critic
            data["critic"] = {"enable_critic": data.pop("enable_critic")}
            migrated = True

        # Also migrate other legacy top-level critic fields if present
        legacy_critic_fields = [
            "enable_iterative_refinement",
            "critic_threshold",
            "issue_threshold",
            "max_refinement_iterations",
        ]
        for field in legacy_critic_fields:
            if field in data:
                if "critic" not in data:
                    data["critic"] = {}
                data["critic"][field] = data.pop(field)
                migrated = True

        return data, migrated

    @classmethod
    def load(cls) -> "CliSettings":
        """Load CLI settings from file.

        Automatically migrates legacy settings format if detected.

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

            # Migrate legacy settings format if needed
            migrated_data, was_migrated = cls._migrate_legacy_settings(data)

            settings = cls.model_validate(migrated_data)

            # Save migrated settings back to disk if migration occurred
            if was_migrated:
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
