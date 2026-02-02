"""CLI settings models and utilities."""

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


# Default threshold for iterative refinement (50%)
DEFAULT_CRITIC_THRESHOLD = 0.5


class CliSettings(BaseModel):
    """Model for CLI-level settings."""

    default_cells_expanded: bool = True
    auto_open_plan_panel: bool = True
    enable_critic: bool = True
    enable_iterative_refinement: bool = Field(
        default=False,
        description=(
            "When enabled, if the critic score is below the threshold, "
            "a message is sent to the agent to review and improve its work."
        ),
    )
    critic_threshold: float = Field(
        default=DEFAULT_CRITIC_THRESHOLD,
        ge=0.0,
        le=1.0,
        description=(
            "The critic score threshold for iterative refinement. "
            "If score is below this threshold, refinement is triggered."
        ),
    )

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
