import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from openhands_cli.stores import CliSettings, CriticSettings


class TestCliSettings:
    def test_defaults(self):
        cfg = CliSettings()
        assert cfg.default_cells_expanded is False
        assert cfg.auto_open_plan_panel is True
        assert cfg.critic.enable_critic is True
        assert cfg.critic.enable_iterative_refinement is False
        assert cfg.critic.critic_threshold == 0.6
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


class TestCliSettingsMigration:
    """Tests for legacy settings format migration."""

    def test_migrate_legacy_flat_format(self, tmp_path: Path):
        """Test that legacy flat format is migrated to nested CriticSettings."""
        config_path = tmp_path / "cli_config.json"
        # Write legacy flat format
        legacy_data = {
            "default_cells_expanded": True,
            "auto_open_plan_panel": False,
            "enable_critic": False,
            "enable_iterative_refinement": True,
            "critic_threshold": 0.75,
        }
        config_path.write_text(json.dumps(legacy_data))

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg = CliSettings.load()

            # Verify values were migrated correctly
            assert cfg.default_cells_expanded is True
            assert cfg.auto_open_plan_panel is False
            assert cfg.critic.enable_critic is False
            assert cfg.critic.enable_iterative_refinement is True
            assert cfg.critic.critic_threshold == 0.75

            # Verify file was re-saved in new format
            saved_data = json.loads(config_path.read_text())
            assert "critic" in saved_data
            assert "enable_critic" not in saved_data  # removed from top level
            assert saved_data["critic"]["enable_critic"] is False

    def test_migrate_partial_legacy_format(self, tmp_path: Path):
        """Test migration when only some critic fields are present."""
        config_path = tmp_path / "cli_config.json"
        # Write legacy format with only enable_critic
        legacy_data = {
            "default_cells_expanded": False,
            "enable_critic": True,
        }
        config_path.write_text(json.dumps(legacy_data))

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg = CliSettings.load()

            # Verify enable_critic was migrated, others use defaults
            assert cfg.critic.enable_critic is True
            assert cfg.critic.enable_iterative_refinement is False  # default
            assert cfg.critic.critic_threshold == 0.6  # default

    def test_new_format_not_migrated(self, tmp_path: Path):
        """Test that new nested format is loaded without migration."""
        config_path = tmp_path / "cli_config.json"
        # Write new nested format
        new_data = {
            "default_cells_expanded": True,
            "critic": {
                "enable_critic": False,
                "enable_iterative_refinement": True,
                "critic_threshold": 0.5,
            },
        }
        original_content = json.dumps(new_data)
        config_path.write_text(original_content)

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg = CliSettings.load()

            # Verify values loaded correctly
            assert cfg.default_cells_expanded is True
            assert cfg.critic.enable_critic is False
            assert cfg.critic.enable_iterative_refinement is True
            assert cfg.critic.critic_threshold == 0.5

            # File should not have been rewritten (no migration needed)
            # Note: we can't easily test this since save() always writes,
            # but we can verify the content is equivalent
            saved_data = json.loads(config_path.read_text())
            assert saved_data == new_data
