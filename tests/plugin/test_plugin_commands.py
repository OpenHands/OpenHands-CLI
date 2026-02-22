"""Tests for plugin CLI commands."""

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def sample_plugin_dir(tmp_path: Path) -> Path:
    """Create a sample plugin directory structure."""
    plugin_dir = tmp_path / "sample-plugin"
    plugin_dir.mkdir(parents=True)

    # Create plugin manifest
    manifest_dir = plugin_dir / ".plugin"
    manifest_dir.mkdir()
    manifest = {
        "name": "sample-plugin",
        "version": "1.0.0",
        "description": "A sample plugin for testing",
    }
    (manifest_dir / "plugin.json").write_text(json.dumps(manifest))

    return plugin_dir


class TestPluginParser:
    """Tests for plugin argument parser."""

    def test_plugin_parser_added(self):
        """Test that plugin subcommand is available."""
        from openhands_cli.argparsers.main_parser import create_main_parser

        parser = create_main_parser()
        args = parser.parse_args(["plugin", "list"])
        assert args.command == "plugin"
        assert args.plugin_command == "list"

    def test_plugin_install_args(self):
        """Test plugin install command arguments."""
        from openhands_cli.argparsers.main_parser import create_main_parser

        parser = create_main_parser()
        args = parser.parse_args(
            ["plugin", "install", "github:owner/repo", "--ref", "v1.0.0", "--force"]
        )
        assert args.command == "plugin"
        assert args.plugin_command == "install"
        assert args.source == "github:owner/repo"
        assert args.ref == "v1.0.0"
        assert args.force is True

    def test_plugin_uninstall_args(self):
        """Test plugin uninstall command arguments."""
        from openhands_cli.argparsers.main_parser import create_main_parser

        parser = create_main_parser()
        args = parser.parse_args(["plugin", "uninstall", "my-plugin"])
        assert args.command == "plugin"
        assert args.plugin_command == "uninstall"
        assert args.name == "my-plugin"

    def test_plugin_update_args(self):
        """Test plugin update command arguments."""
        from openhands_cli.argparsers.main_parser import create_main_parser

        parser = create_main_parser()
        args = parser.parse_args(["plugin", "update", "my-plugin"])
        assert args.command == "plugin"
        assert args.plugin_command == "update"
        assert args.name == "my-plugin"


class TestPluginCommands:
    """Tests for plugin command handlers."""

    @patch("openhands.sdk.plugin.list_installed_plugins")
    @patch("openhands.sdk.plugin.get_installed_plugins_dir")
    def test_handle_list_empty(self, mock_get_dir, mock_list, capsys):
        """Test listing plugins when none are installed."""
        from openhands_cli.plugin.commands import handle_plugin_command

        mock_list.return_value = []
        mock_get_dir.return_value = Path("/home/user/.openhands/skills/installed")

        args = Namespace(plugin_command="list", json=False)
        handle_plugin_command(args)

        captured = capsys.readouterr()
        assert "No plugins installed" in captured.out

    @patch("openhands.sdk.plugin.list_installed_plugins")
    @patch("openhands.sdk.plugin.get_installed_plugins_dir")
    def test_handle_list_json(self, mock_get_dir, mock_list, capsys):
        """Test listing plugins with JSON output."""
        from openhands.sdk.plugin import InstalledPluginInfo
        from openhands_cli.plugin.commands import handle_plugin_command

        mock_info = InstalledPluginInfo(
            name="test-plugin",
            version="1.0.0",
            description="Test",
            source="github:owner/test",
            installed_at="2024-01-01T00:00:00Z",
            install_path="/path/to/plugin",
        )
        mock_list.return_value = [mock_info]
        mock_get_dir.return_value = Path("/home/user/.openhands/skills/installed")

        args = Namespace(plugin_command="list", json=True)
        handle_plugin_command(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "plugins" in output
        assert len(output["plugins"]) == 1
        assert output["plugins"][0]["name"] == "test-plugin"

    @patch("openhands.sdk.plugin.install_plugin")
    def test_handle_install_success(self, mock_install, capsys):
        """Test successful plugin installation."""
        from openhands.sdk.plugin import InstalledPluginInfo
        from openhands_cli.plugin.commands import handle_plugin_command

        mock_info = InstalledPluginInfo(
            name="new-plugin",
            version="1.0.0",
            description="New plugin",
            source="github:owner/new-plugin",
            resolved_ref="abc123def456",
            installed_at="2024-01-01T00:00:00Z",
            install_path="/path/to/plugin",
        )
        mock_install.return_value = mock_info

        args = Namespace(
            plugin_command="install",
            source="github:owner/new-plugin",
            ref=None,
            repo_path=None,
            force=False,
        )
        handle_plugin_command(args)

        captured = capsys.readouterr()
        assert "Successfully installed" in captured.out
        assert "new-plugin" in captured.out

    @patch("openhands.sdk.plugin.install_plugin")
    def test_handle_install_already_exists(self, mock_install, capsys):
        """Test installation when plugin already exists."""
        from openhands_cli.plugin.commands import handle_plugin_command

        mock_install.side_effect = FileExistsError("Plugin already installed")

        args = Namespace(
            plugin_command="install",
            source="github:owner/existing",
            ref=None,
            repo_path=None,
            force=False,
        )

        with pytest.raises(SystemExit) as exc_info:
            handle_plugin_command(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "already installed" in captured.out or "Use --force" in captured.out

    @patch("openhands.sdk.plugin.uninstall_plugin")
    def test_handle_uninstall_success(self, mock_uninstall, capsys):
        """Test successful plugin uninstallation."""
        from openhands_cli.plugin.commands import handle_plugin_command

        mock_uninstall.return_value = True

        args = Namespace(plugin_command="uninstall", name="old-plugin")
        handle_plugin_command(args)

        captured = capsys.readouterr()
        assert "Successfully uninstalled" in captured.out
        assert "old-plugin" in captured.out

    @patch("openhands.sdk.plugin.uninstall_plugin")
    def test_handle_uninstall_not_found(self, mock_uninstall, capsys):
        """Test uninstalling a plugin that doesn't exist."""
        from openhands_cli.plugin.commands import handle_plugin_command

        mock_uninstall.return_value = False

        args = Namespace(plugin_command="uninstall", name="nonexistent")

        with pytest.raises(SystemExit) as exc_info:
            handle_plugin_command(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not installed" in captured.out

    @patch("openhands.sdk.plugin.update_plugin")
    def test_handle_update_success(self, mock_update, capsys):
        """Test successful plugin update."""
        from openhands.sdk.plugin import InstalledPluginInfo
        from openhands_cli.plugin.commands import handle_plugin_command

        mock_info = InstalledPluginInfo(
            name="my-plugin",
            version="2.0.0",
            description="Updated plugin",
            source="github:owner/my-plugin",
            resolved_ref="newcommit123",
            installed_at="2024-01-02T00:00:00Z",
            install_path="/path/to/plugin",
        )
        mock_update.return_value = mock_info

        args = Namespace(plugin_command="update", name="my-plugin")
        handle_plugin_command(args)

        captured = capsys.readouterr()
        assert "Successfully updated" in captured.out
        assert "my-plugin" in captured.out

    @patch("openhands.sdk.plugin.update_plugin")
    def test_handle_update_not_found(self, mock_update, capsys):
        """Test updating a plugin that doesn't exist."""
        from openhands_cli.plugin.commands import handle_plugin_command

        mock_update.return_value = None

        args = Namespace(plugin_command="update", name="nonexistent")

        with pytest.raises(SystemExit) as exc_info:
            handle_plugin_command(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not installed" in captured.out

    def test_handle_no_subcommand(self, capsys):
        """Test plugin command without subcommand shows help."""
        from openhands_cli.plugin.commands import handle_plugin_command

        args = Namespace(plugin_command=None)
        handle_plugin_command(args)

        captured = capsys.readouterr()
        assert "Usage:" in captured.out
        assert "list" in captured.out
        assert "install" in captured.out
