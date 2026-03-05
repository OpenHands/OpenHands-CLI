"""Tests for marketplace_path setting persistence in CliSettings."""

from unittest.mock import patch

from openhands_cli.stores import CliSettings


class TestMarketplacePathSettings:
    """Tests for marketplace_path setting storage and defaults."""

    def test_marketplace_path_stored_correctly_in_settings(self, tmp_path):
        """Verify marketplace_path is persisted correctly in CliSettings."""
        config_path = tmp_path / "cli_config.json"

        with patch.object(CliSettings, "get_config_path", return_value=config_path):
            # Test saving None (default - load all skills)
            settings = CliSettings(marketplace_path=None)
            settings.save()
            loaded = CliSettings.load()
            assert loaded.marketplace_path is None

            # Test saving custom path
            settings = CliSettings(marketplace_path="custom/path.json")
            settings.save()
            loaded = CliSettings.load()
            assert loaded.marketplace_path == "custom/path.json"

    def test_cli_settings_default_marketplace_path_is_none(self):
        """Verify default marketplace_path is None (load all skills)."""
        settings = CliSettings()
        assert settings.marketplace_path is None
