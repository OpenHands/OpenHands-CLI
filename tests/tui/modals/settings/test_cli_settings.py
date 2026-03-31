import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from openhands_cli.stores import CliSettings, CriticSettings


class TestCriticSettingsValidation:
    def test_valid_threshold_settings(self) -> None:
        settings = CriticSettings(
            critic_threshold=0.5,
            issue_threshold=0.75,
            max_refinement_iterations=5,
        )

        assert settings.critic_threshold == 0.5
        assert settings.issue_threshold == 0.75
        assert settings.max_refinement_iterations == 5

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"critic_threshold": 1.5},
            {"critic_threshold": -0.1},
            {"issue_threshold": 5.0},
            {"issue_threshold": -0.5},
            {"max_refinement_iterations": 0},
        ],
    )
    def test_invalid_verification_values_raise(
        self, kwargs: dict[str, float | int]
    ) -> None:
        with pytest.raises(ValidationError):
            CriticSettings(**kwargs)


class TestCliSettings:
    def test_defaults(self) -> None:
        cfg = CliSettings()

        assert cfg.default_cells_expanded is False
        assert cfg.auto_open_plan_panel is True
        assert cfg.critic is None

    @pytest.mark.parametrize("value", [True, False])
    def test_default_cells_expanded_accepts_bool(self, value: bool) -> None:
        cfg = CliSettings(default_cells_expanded=value)
        assert cfg.default_cells_expanded is value

    @pytest.mark.parametrize(
        "env_value, expected",
        [
            ("/custom/path", Path("/custom/path") / "cli_config.json"),
            ("~/test", Path("~/test") / "cli_config.json"),
            ("", Path("") / "cli_config.json"),
            ("   ", Path("   ") / "cli_config.json"),
        ],
    )
    def test_get_config_path_uses_env_value_as_is(
        self, env_value: str, expected: Path
    ) -> None:
        with patch.dict(os.environ, {"PERSISTENCE_DIR": env_value}):
            assert CliSettings.get_config_path() == expected

    def test_get_config_path_default_uses_expanduser(self) -> None:
        env = os.environ.copy()
        env.pop("PERSISTENCE_DIR", None)

        with patch.dict(os.environ, env, clear=True):
            with patch(
                "os.path.expanduser", return_value="/home/user/.openhands"
            ) as expanduser:
                path = CliSettings.get_config_path()
                assert path == Path("/home/user/.openhands/cli_config.json")
                expanduser.assert_called_once_with("~/.openhands")

    def test_load_returns_defaults_when_file_missing(self, tmp_path: Path) -> None:
        config_path = tmp_path / "cli_config.json"
        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg = CliSettings.load()
        assert cfg == CliSettings()

    @pytest.mark.parametrize(
        "file_content, expected",
        [
            (json.dumps({"default_cells_expanded": True}), True),
            (json.dumps({"default_cells_expanded": False}), False),
            (json.dumps({}), False),
            ("not json", False),
            (json.dumps({"default_cells_expanded": "nope"}), False),
            (json.dumps({"unknown_field": True}), False),
        ],
    )
    def test_load_various_inputs(
        self, tmp_path: Path, file_content: str, expected: bool
    ) -> None:
        config_path = tmp_path / "cli_config.json"
        config_path.write_text(file_content)

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg = CliSettings.load()

        assert cfg.default_cells_expanded is expected

    def test_load_permission_error_propagates(self, tmp_path: Path) -> None:
        config_path = tmp_path / "cli_config.json"
        config_path.write_text(json.dumps({"default_cells_expanded": True}))

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                with pytest.raises(PermissionError):
                    CliSettings.load()

    @pytest.mark.parametrize("value", [True, False])
    def test_save_creates_parent_dir_and_roundtrips(
        self, tmp_path: Path, value: bool
    ) -> None:
        config_path = tmp_path / "nested" / "dir" / "cli_config.json"
        cfg = CliSettings(default_cells_expanded=value)

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg.save()
            assert config_path.exists()
            loaded = CliSettings.load()

        assert loaded.default_cells_expanded is value
        assert loaded.critic is None

    def test_save_writes_only_cli_owned_fields(self, tmp_path: Path) -> None:
        config_path = tmp_path / "cli_config.json"
        cfg = CliSettings(
            default_cells_expanded=False,
            auto_open_plan_panel=False,
            critic=CriticSettings(
                critic_enabled=False,
                enable_iterative_refinement=True,
                critic_threshold=0.6,
                issue_threshold=0.75,
                max_refinement_iterations=3,
            ),
        )

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg.save()

        assert json.loads(config_path.read_text()) == {
            "default_cells_expanded": False,
            "auto_open_plan_panel": False,
        }

    def test_save_permission_error_propagates(self, tmp_path: Path) -> None:
        config_path = tmp_path / "cli_config.json"
        cfg = CliSettings(default_cells_expanded=True)

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                with pytest.raises(PermissionError):
                    cfg.save()


class TestCliSettingsMigration:
    def test_migrate_legacy_critic_enabled_at_top_level(self, tmp_path: Path) -> None:
        config_path = tmp_path / "cli_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "default_cells_expanded": True,
                    "critic_enabled": False,
                }
            )
        )

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg = CliSettings.load()

        assert cfg.default_cells_expanded is True
        assert cfg.critic is not None
        assert cfg.critic.critic_enabled is False
        assert json.loads(config_path.read_text())["critic_enabled"] is False

    def test_migrate_multiple_legacy_critic_fields(self, tmp_path: Path) -> None:
        config_path = tmp_path / "cli_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "default_cells_expanded": False,
                    "critic_enabled": True,
                    "enable_iterative_refinement": True,
                    "critic_threshold": 0.7,
                    "issue_threshold": 0.8,
                    "max_refinement_iterations": 5,
                }
            )
        )

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg = CliSettings.load()

        assert cfg.critic is not None
        assert cfg.critic.critic_enabled is True
        assert cfg.critic.enable_iterative_refinement is True
        assert cfg.critic.critic_threshold == 0.7
        assert cfg.critic.issue_threshold == 0.8
        assert cfg.critic.max_refinement_iterations == 5

    def test_new_nested_critic_format_loads_as_compatibility_field(
        self, tmp_path: Path
    ) -> None:
        config_path = tmp_path / "cli_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "default_cells_expanded": True,
                    "critic": {
                        "critic_enabled": False,
                        "enable_iterative_refinement": True,
                        "critic_threshold": 0.5,
                    },
                }
            )
        )

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg = CliSettings.load()

        assert cfg.critic is not None
        assert cfg.critic.critic_enabled is False
        assert cfg.critic.enable_iterative_refinement is True
        assert cfg.critic.critic_threshold == 0.5
