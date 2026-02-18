import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from openhands_cli.stores import CliSettings, CriticSettings


class TestCriticSettingsValidation:
    """Tests for CriticSettings field validators."""

    def test_valid_critic_threshold(self):
        """Verify valid critic_threshold values are accepted."""
        settings = CriticSettings(critic_threshold=0.5)
        assert settings.critic_threshold == 0.5

    def test_valid_critic_threshold_boundaries(self):
        """Verify boundary values for critic_threshold are accepted."""
        settings_min = CriticSettings(critic_threshold=0.0)
        settings_max = CriticSettings(critic_threshold=1.0)
        assert settings_min.critic_threshold == 0.0
        assert settings_max.critic_threshold == 1.0

    def test_invalid_critic_threshold_too_high(self):
        """Verify critic_threshold > 1.0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CriticSettings(critic_threshold=1.5)
        assert "Threshold must be between 0.0 and 1.0" in str(exc_info.value)

    def test_invalid_critic_threshold_negative(self):
        """Verify negative critic_threshold raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CriticSettings(critic_threshold=-0.1)
        assert "Threshold must be between 0.0 and 1.0" in str(exc_info.value)

    def test_valid_issue_threshold(self):
        """Verify valid issue_threshold values are accepted."""
        settings = CriticSettings(issue_threshold=0.75)
        assert settings.issue_threshold == 0.75

    def test_invalid_issue_threshold_too_high(self):
        """Verify issue_threshold > 1.0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CriticSettings(issue_threshold=5.0)
        assert "Threshold must be between 0.0 and 1.0" in str(exc_info.value)

    def test_invalid_issue_threshold_negative(self):
        """Verify negative issue_threshold raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CriticSettings(issue_threshold=-0.5)
        assert "Threshold must be between 0.0 and 1.0" in str(exc_info.value)

    def test_valid_max_refinement_iterations(self):
        """Verify valid max_refinement_iterations values are accepted."""
        settings = CriticSettings(max_refinement_iterations=5)
        assert settings.max_refinement_iterations == 5

    def test_valid_max_refinement_iterations_boundaries(self):
        """Verify boundary values for max_refinement_iterations are accepted."""
        settings_min = CriticSettings(max_refinement_iterations=1)
        settings_max = CriticSettings(max_refinement_iterations=10)
        assert settings_min.max_refinement_iterations == 1
        assert settings_max.max_refinement_iterations == 10

    def test_invalid_max_refinement_iterations_too_high(self):
        """Verify max_refinement_iterations > 10 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CriticSettings(max_refinement_iterations=100)
        assert "Max iterations must be between 1 and 10" in str(exc_info.value)

    def test_invalid_max_refinement_iterations_zero(self):
        """Verify max_refinement_iterations = 0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CriticSettings(max_refinement_iterations=0)
        assert "Max iterations must be between 1 and 10" in str(exc_info.value)

    def test_invalid_max_refinement_iterations_negative(self):
        """Verify negative max_refinement_iterations raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CriticSettings(max_refinement_iterations=-1)
        assert "Max iterations must be between 1 and 10" in str(exc_info.value)


class TestCliSettings:
    def test_defaults(self):
        cfg = CliSettings()
        assert cfg.default_cells_expanded is False
        assert cfg.auto_open_plan_panel is True
        assert cfg.critic.enable_critic is True
        assert cfg.critic.enable_iterative_refinement is False
        assert cfg.critic.critic_threshold == 0.6
        assert cfg.critic.issue_threshold == 0.75
        assert cfg.critic.max_refinement_iterations == 3

    @pytest.mark.parametrize("value", [True, False])
    def test_default_cells_expanded_accepts_bool(self, value: bool):
        cfg = CliSettings(default_cells_expanded=value)
        assert cfg.default_cells_expanded is value

    @pytest.mark.parametrize(
        "env_value, expected",
        [
            ("/custom/path", Path("/custom/path") / "cli_config.json"),
            ("~/test", Path("~/test") / "cli_config.json"),  # env value is used as-is
            ("", Path("") / "cli_config.json"),
            ("   ", Path("   ") / "cli_config.json"),
        ],
    )
    def test_get_config_path_uses_env_value_as_is(self, env_value: str, expected: Path):
        with patch.dict(os.environ, {"PERSISTENCE_DIR": env_value}):
            assert CliSettings.get_config_path() == expected

    def test_get_config_path_default_uses_expanduser(self):
        # Ensure env var is not set, then assert expanduser is used for default.
        env = os.environ.copy()
        env.pop("PERSISTENCE_DIR", None)

        with patch.dict(os.environ, env, clear=True):
            with patch(
                "os.path.expanduser", return_value="/home/user/.openhands"
            ) as ex:
                path = CliSettings.get_config_path()
                assert path == Path("/home/user/.openhands/cli_config.json")
                ex.assert_called_once_with("~/.openhands")

    def test_load_returns_defaults_when_file_missing(self, tmp_path: Path):
        config_path = tmp_path / "cli_config.json"
        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg = CliSettings.load()
        assert cfg == CliSettings()

    @pytest.mark.parametrize(
        "file_content, expected",
        [
            (json.dumps({"default_cells_expanded": True}), True),
            (json.dumps({"default_cells_expanded": False}), False),
            (json.dumps({}), False),  # missing field -> default
            ("not json", False),  # JSONDecodeError -> defaults
            (
                json.dumps({"default_cells_expanded": "nope"}),
                False,
            ),  # ValidationError -> caught -> defaults
            (
                json.dumps({"unknown_field": True}),
                False,
            ),  # extra ignored; still default False
        ],
    )
    def test_load_various_inputs(
        self, tmp_path: Path, file_content: str, expected: bool
    ):
        config_path = tmp_path / "cli_config.json"
        config_path.write_text(file_content)

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg = CliSettings.load()

        assert cfg.default_cells_expanded is expected

    def test_load_permission_error_propagates(self, tmp_path: Path):
        config_path = tmp_path / "cli_config.json"
        config_path.write_text(json.dumps({"default_cells_expanded": True}))

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                with pytest.raises(PermissionError):
                    CliSettings.load()

    @pytest.mark.parametrize("value", [True, False])
    def test_save_creates_parent_dir_and_roundtrips(self, tmp_path: Path, value: bool):
        config_path = tmp_path / "nested" / "dir" / "cli_config.json"
        cfg = CliSettings(default_cells_expanded=value)

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg.save()
            assert config_path.exists()
            loaded = CliSettings.load()

        assert loaded.default_cells_expanded is value

    def test_save_writes_expected_json_format(self, tmp_path: Path):
        config_path = tmp_path / "cli_config.json"
        cfg = CliSettings(
            default_cells_expanded=False,
            auto_open_plan_panel=False,
            critic=CriticSettings(
                enable_critic=False,
                enable_iterative_refinement=False,
                critic_threshold=0.6,
                issue_threshold=0.75,
                max_refinement_iterations=3,
            ),
        )

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg.save()

        assert config_path.read_text() == json.dumps(
            {
                "default_cells_expanded": False,
                "auto_open_plan_panel": False,
                "critic": {
                    "enable_critic": False,
                    "enable_iterative_refinement": False,
                    "critic_threshold": 0.6,
                    "issue_threshold": 0.75,
                    "max_refinement_iterations": 3,
                },
            },
            indent=2,
        )

    def test_save_permission_error_propagates(self, tmp_path: Path):
        config_path = tmp_path / "cli_config.json"
        cfg = CliSettings(default_cells_expanded=True)

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                with pytest.raises(PermissionError):
                    cfg.save()
