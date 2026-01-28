"""Tests for the plugin loader module."""

import json

import pytest

from openhands_cli.plugins.plugin_loader import (
    _create_skill_from_plugin,
    _find_plugin_in_index,
    load_enabled_plugins,
)
from openhands_cli.plugins.plugin_storage import InstalledPlugin


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory for tests."""
    config_dir = tmp_path / ".openhands"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Patch the PERSISTENCE_DIR and cache directories
    monkeypatch.setattr(
        "openhands_cli.plugins.plugin_storage.PERSISTENCE_DIR", str(config_dir)
    )
    monkeypatch.setattr(
        "openhands_cli.plugins.plugin_storage.INSTALLED_PLUGINS_FILE",
        str(config_dir / "plugins.json"),
    )
    monkeypatch.setattr(
        "openhands_cli.plugins.marketplace_storage.PERSISTENCE_DIR", str(config_dir)
    )
    monkeypatch.setattr(
        "openhands_cli.plugins.marketplace_storage.MARKETPLACES_FILE",
        str(config_dir / "marketplaces.json"),
    )
    monkeypatch.setattr(
        "openhands_cli.plugins.marketplace_storage.MARKETPLACE_CACHE_DIR",
        str(config_dir / "marketplace_cache"),
    )

    return config_dir


class TestFindPluginInIndex:
    """Tests for _find_plugin_in_index function."""

    def test_find_existing_plugin(self):
        """Test finding a plugin that exists in the index."""
        index = {
            "plugins": [
                {"name": "plugin-a", "description": "Plugin A"},
                {"name": "plugin-b", "description": "Plugin B"},
            ]
        }

        result = _find_plugin_in_index("plugin-a", index)
        assert result is not None
        assert result["name"] == "plugin-a"
        assert result["description"] == "Plugin A"

    def test_find_nonexistent_plugin(self):
        """Test finding a plugin that doesn't exist."""
        index = {
            "plugins": [
                {"name": "plugin-a", "description": "Plugin A"},
            ]
        }

        result = _find_plugin_in_index("plugin-x", index)
        assert result is None

    def test_find_in_empty_index(self):
        """Test finding a plugin in an empty index."""
        index = {"plugins": []}

        result = _find_plugin_in_index("plugin-a", index)
        assert result is None

    def test_find_in_index_without_plugins_key(self):
        """Test finding a plugin when plugins key is missing."""
        index = {}

        result = _find_plugin_in_index("plugin-a", index)
        assert result is None


class TestCreateSkillFromPlugin:
    """Tests for _create_skill_from_plugin function."""

    def test_create_skill_with_description_and_instructions(self):
        """Test creating a skill with both description and instructions."""
        plugin = InstalledPlugin(
            name="test-plugin",
            marketplace="test-marketplace",
        )
        plugin_def = {
            "name": "test-plugin",
            "description": "This is a test plugin.",
            "instructions": "Use this plugin for testing.",
        }

        skill = _create_skill_from_plugin(plugin, plugin_def)

        assert skill.name == "plugin:test-plugin@test-marketplace"
        assert "This is a test plugin." in skill.content
        assert "Use this plugin for testing." in skill.content

    def test_create_skill_with_description_only(self):
        """Test creating a skill with only description."""
        plugin = InstalledPlugin(
            name="test-plugin",
            marketplace="test-marketplace",
        )
        plugin_def = {
            "name": "test-plugin",
            "description": "This is a test plugin.",
        }

        skill = _create_skill_from_plugin(plugin, plugin_def)

        assert skill.name == "plugin:test-plugin@test-marketplace"
        assert "This is a test plugin." in skill.content

    def test_create_skill_with_no_content(self):
        """Test creating a skill when plugin has no description/instructions."""
        plugin = InstalledPlugin(
            name="test-plugin",
            marketplace="test-marketplace",
        )
        plugin_def = {
            "name": "test-plugin",
        }

        skill = _create_skill_from_plugin(plugin, plugin_def)

        assert skill.name == "plugin:test-plugin@test-marketplace"
        assert "test-plugin" in skill.content
        assert "enabled" in skill.content

    def test_create_skill_uses_description_field(self):
        """Test that skill's description field is set from plugin definition."""
        plugin = InstalledPlugin(
            name="test-plugin",
            marketplace="test-marketplace",
        )
        plugin_def = {
            "name": "test-plugin",
            "description": "A brief description of the plugin",
            "instructions": "How to use this plugin",
        }

        skill = _create_skill_from_plugin(plugin, plugin_def)

        assert skill.description == "A brief description of the plugin"


class TestLoadEnabledPlugins:
    """Tests for load_enabled_plugins function."""

    def test_load_no_enabled_plugins(self, temp_config_dir):
        """Test loading when no plugins are enabled."""
        # Create empty plugins.json
        plugins_file = temp_config_dir / "plugins.json"
        plugins_file.write_text(json.dumps({"installed": {}}))

        skills = load_enabled_plugins()
        assert skills == []

    def test_load_enabled_plugin_with_cached_index(self, temp_config_dir):
        """Test loading an enabled plugin with a cached marketplace index."""
        # Create plugins.json with one enabled plugin
        plugins_file = temp_config_dir / "plugins.json"
        plugins_file.write_text(
            json.dumps(
                {
                    "installed": {
                        "test-plugin@test-marketplace": {
                            "name": "test-plugin",
                            "marketplace": "test-marketplace",
                            "enabled": True,
                        }
                    }
                }
            )
        )

        # Create marketplaces.json
        marketplaces_file = temp_config_dir / "marketplaces.json"
        marketplaces_file.write_text(
            json.dumps(
                {
                    "marketplaces": {
                        "test-marketplace": {
                            "source": {"source": "url", "url": "http://example.com"},
                        }
                    }
                }
            )
        )

        # Create cached marketplace index
        cache_dir = temp_config_dir / "marketplace_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "test-marketplace.json"
        cache_file.write_text(
            json.dumps(
                {
                    "plugins": [
                        {
                            "name": "test-plugin",
                            "description": "A test plugin for testing",
                            "instructions": "Use for testing purposes",
                        }
                    ]
                }
            )
        )

        skills = load_enabled_plugins()

        assert len(skills) == 1
        assert skills[0].name == "plugin:test-plugin@test-marketplace"
        assert "A test plugin for testing" in skills[0].content

    def test_load_disabled_plugin_not_loaded(self, temp_config_dir):
        """Test that disabled plugins are not loaded."""
        # Create plugins.json with one disabled plugin
        plugins_file = temp_config_dir / "plugins.json"
        plugins_file.write_text(
            json.dumps(
                {
                    "installed": {
                        "test-plugin@test-marketplace": {
                            "name": "test-plugin",
                            "marketplace": "test-marketplace",
                            "enabled": False,
                        }
                    }
                }
            )
        )

        skills = load_enabled_plugins()
        assert skills == []

    def test_load_plugin_without_cached_index(self, temp_config_dir):
        """Test loading a plugin when marketplace index is not cached."""
        # Create plugins.json with one enabled plugin
        plugins_file = temp_config_dir / "plugins.json"
        plugins_file.write_text(
            json.dumps(
                {
                    "installed": {
                        "test-plugin@test-marketplace": {
                            "name": "test-plugin",
                            "marketplace": "test-marketplace",
                            "enabled": True,
                        }
                    }
                }
            )
        )

        # Don't create cached index - plugin should fail to load gracefully
        skills = load_enabled_plugins()
        assert skills == []  # Plugin fails to load, returns empty list
