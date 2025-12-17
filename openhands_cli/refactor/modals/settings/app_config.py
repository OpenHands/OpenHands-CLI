"""App configuration models and utilities."""

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class AppConfiguration(BaseModel):
    """Model for application-level configurations."""
    
    display_cost_per_action: bool = False
    
    @classmethod
    def get_config_path(cls) -> Path:
        """Get the path to the CLI configuration file."""
        # Use environment variable if set, otherwise use default
        persistence_dir = os.environ.get('PERSISTENCE_DIR', os.path.expanduser("~/.openhands"))
        return Path(persistence_dir) / "cli_config.json"
    
    @classmethod
    def load(cls) -> "AppConfiguration":
        """Load app configuration from file.
        
        Returns:
            AppConfiguration instance with loaded settings, or defaults if file doesn't exist
        """
        config_path = cls.get_config_path()
        
        if not config_path.exists():
            return cls()
        
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
            return cls.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            # If file is corrupted, return defaults
            return cls()
    
    def save(self) -> None:
        """Save app configuration to file."""
        config_path = self.get_config_path()
        
        # Ensure the persistence directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)


class AppConfigSaveResult(BaseModel):
    """Result of attempting to save app configuration."""
    
    success: bool
    error_message: str | None = None


def save_app_config(config: AppConfiguration) -> AppConfigSaveResult:
    """Save app configuration with error handling.
    
    Args:
        config: The app configuration to save
        
    Returns:
        AppConfigSaveResult indicating success or failure
    """
    try:
        config.save()
        return AppConfigSaveResult(success=True)
    except Exception as e:
        return AppConfigSaveResult(success=False, error_message=str(e))