"""CLI settings models and utilities."""

import json
import os
from pathlib import Path

from pydantic import BaseModel, field_validator


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
    def load(cls) -> "CliSettings":
        """Load CLI settings from file.

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

            return cls.model_validate(data)
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
