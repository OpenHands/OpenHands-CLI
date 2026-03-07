"""Tests for marketplace_path setting persistence in CliSettings."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

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

    def test_marketplace_path_trims_whitespace(self):
        settings = CliSettings(marketplace_path="  marketplaces/custom.json  ")
        assert settings.marketplace_path == "marketplaces/custom.json"

    def test_marketplace_path_blank_string_maps_to_none(self):
        settings = CliSettings(marketplace_path="   ")
        assert settings.marketplace_path is None

    @pytest.mark.parametrize(
        "value",
        [
            "/marketplaces/default.json",
            "../secret.json",
            "owner/repo:path/to/marketplace.json",
            "marketplaces\\default.json",
            "marketplaces/default",
            "marketplaces/%2e%2e/secret.json",
        ],
    )
    def test_marketplace_path_rejects_invalid_values(self, value: str):
        with pytest.raises(ValidationError):
            CliSettings(marketplace_path=value)
