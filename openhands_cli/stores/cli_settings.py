"""CLI settings models and utilities."""

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from openhands.sdk.settings import VerificationSettings


class CriticSettings(VerificationSettings):
    issue_threshold: float = 0.75

    @field_validator("issue_threshold")
    @classmethod
    def validate_issue_threshold(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {value}")
        return value


DEFAULT_CRITIC_THRESHOLD = float(
    CriticSettings.model_fields["critic_threshold"].default
)
DEFAULT_ISSUE_THRESHOLD = float(CriticSettings.model_fields["issue_threshold"].default)
DEFAULT_MAX_REFINEMENT_ITERATIONS = int(
    CriticSettings.model_fields["max_refinement_iterations"].default
)


class CliSettings(BaseModel):
    """Model for CLI-owned UI settings.

    The ``critic`` field is a compatibility shim for older ``cli_config.json``
    files that persisted agent-behavior settings before they moved into the SDK's
    ``VerificationSettings`` model. It is intentionally excluded from new writes.
    """

    default_cells_expanded: bool = False
    auto_open_plan_panel: bool = True
    critic: CriticSettings | None = Field(default=None, exclude=True)

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the path to the CLI configuration file."""
        persistence_dir = os.environ.get(
            "PERSISTENCE_DIR", os.path.expanduser("~/.openhands")
        )
        return Path(persistence_dir) / "cli_config.json"

    @classmethod
    def _migrate_legacy_settings(cls, data: dict) -> tuple[dict, bool]:
        """Migrate legacy critic settings into the compatibility field."""
        migrated = False

        if "critic" not in data:
            if "enable_critic" in data:
                data["critic"] = {"critic_enabled": data.pop("enable_critic")}
                migrated = True
            elif "critic_enabled" in data:
                data["critic"] = {"critic_enabled": data.pop("critic_enabled")}
                migrated = True

        legacy_critic_fields = {
            "enable_iterative_refinement": "enable_iterative_refinement",
            "critic_threshold": "critic_threshold",
            "issue_threshold": "issue_threshold",
            "max_refinement_iterations": "max_refinement_iterations",
        }
        for legacy_key, verification_key in legacy_critic_fields.items():
            if legacy_key in data:
                if "critic" not in data:
                    data["critic"] = {}
                data["critic"][verification_key] = data.pop(legacy_key)
                migrated = True

        return data, migrated

    @classmethod
    def load(cls) -> "CliSettings":
        """Load CLI settings from file."""
        config_path = cls.get_config_path()
        if not config_path.exists():
            return cls()

        try:
            with open(config_path) as f:
                data = json.load(f)

            migrated_data, _ = cls._migrate_legacy_settings(data)
            return cls.model_validate(migrated_data)
        except (json.JSONDecodeError, ValueError):
            return cls()

    def save(self, *, include_critic: bool = False) -> None:
        """Save CLI settings to file.

        Args:
            include_critic: When True, also persist the compatibility critic block.
        """
        config_path = self.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "default_cells_expanded": self.default_cells_expanded,
            "auto_open_plan_panel": self.auto_open_plan_panel,
        }
        if include_critic and self.critic is not None:
            payload["critic"] = self.critic.model_dump(exclude_none=True)

        with open(config_path, "w") as f:
            json.dump(payload, f, indent=2)
