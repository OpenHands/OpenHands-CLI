import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from openhands_cli.stores import CliSettings


class TestCliSettings:
    def test_defaults(self):
        cfg = CliSettings()
        assert cfg.display_cost_per_action is False

    @pytest.mark.parametrize("value", [True, False])
    def test_model_accepts_bool(self, value: bool):
        cfg = CliSettings(display_cost_per_action=value)
        assert cfg.display_cost_per_action is value

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
            (json.dumps({"display_cost_per_action": True}), True),
            (json.dumps({"display_cost_per_action": False}), False),
            (json.dumps({}), False),  # missing field -> default
            ("not json", False),  # JSONDecodeError -> defaults
            (
                json.dumps({"display_cost_per_action": "nope"}),
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

        assert cfg.display_cost_per_action is expected

    def test_load_permission_error_propagates(self, tmp_path: Path):
        config_path = tmp_path / "cli_config.json"
        config_path.write_text(json.dumps({"display_cost_per_action": True}))

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                with pytest.raises(PermissionError):
                    CliSettings.load()

    @pytest.mark.parametrize("value", [True, False])
    def test_save_creates_parent_dir_and_roundtrips(self, tmp_path: Path, value: bool):
        config_path = tmp_path / "nested" / "dir" / "cli_config.json"
        cfg = CliSettings(display_cost_per_action=value)

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg.save()
            assert config_path.exists()
            loaded = CliSettings.load()

        assert loaded.display_cost_per_action is value

    def test_save_writes_expected_json_format(self, tmp_path: Path):
        config_path = tmp_path / "cli_config.json"
        cfg = CliSettings(display_cost_per_action=True)

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            cfg.save()

        assert config_path.read_text() == json.dumps(
            {"display_cost_per_action": True}, indent=2
        )

    def test_save_permission_error_propagates(self, tmp_path: Path):
        config_path = tmp_path / "cli_config.json"
        cfg = CliSettings(display_cost_per_action=True)

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                with pytest.raises(PermissionError):
                    cfg.save()
