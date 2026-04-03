"""Tests for the --plugins-dir CLI argument functionality."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


class TestPluginsDirArgument:
    """Tests for --plugins-dir CLI argument parsing."""

    def test_plugins_dir_in_help(self):
        """Test that --plugins-dir appears in help output."""
        result = subprocess.run(
            [sys.executable, "-m", "openhands_cli.entrypoint", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--plugins-dir" in result.stdout
        assert "Load plugins" in result.stdout

    def test_plugins_dir_single_value(self):
        """Test parsing a single --plugins-dir argument."""
        from openhands_cli.argparsers.main_parser import create_main_parser

        parser = create_main_parser()
        args = parser.parse_args(["--plugins-dir", "/path/to/plugin"])
        assert args.plugins_dir == ["/path/to/plugin"]

    def test_plugins_dir_multiple_values(self):
        """Test parsing multiple --plugins-dir arguments."""
        from openhands_cli.argparsers.main_parser import create_main_parser

        parser = create_main_parser()
        args = parser.parse_args(
            [
                "--plugins-dir",
                "/path/to/plugin1",
                "--plugins-dir",
                "/path/to/plugin2",
            ]
        )
        assert args.plugins_dir == ["/path/to/plugin1", "/path/to/plugin2"]

    def test_plugins_dir_none_when_not_specified(self):
        """Test that plugins_dir is None when not specified."""
        from openhands_cli.argparsers.main_parser import create_main_parser

        parser = create_main_parser()
        args = parser.parse_args([])
        assert args.plugins_dir is None


class TestPluginLoading:
    """Tests for loading plugins from directories."""

    def test_load_plugins_from_nonexistent_dir(self):
        """Test that nonexistent directories are handled gracefully."""
        from openhands_cli.plugins import load_plugins_from_dirs

        plugins = load_plugins_from_dirs(["/nonexistent/path"])
        assert plugins == []

    def test_load_plugins_from_empty_dir(self):
        """Test loading from an empty directory returns no plugins."""
        from openhands_cli.plugins import load_plugins_from_dirs

        with tempfile.TemporaryDirectory() as tmpdir:
            plugins = load_plugins_from_dirs([tmpdir])
            # Empty directory with no plugin manifest should return no plugins
            assert plugins == []

    def test_load_plugins_from_dir_with_plugin(self):
        """Test loading a plugin from a directory with proper structure."""
        from openhands_cli.plugins import load_plugins_from_dirs

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a plugin directory structure
            plugin_dir = Path(tmpdir) / "my-test-plugin"
            plugin_dir.mkdir()

            # Create .plugin directory with plugin.json manifest
            manifest_dir = plugin_dir / ".plugin"
            manifest_dir.mkdir()

            manifest = {
                "name": "test-plugin",
                "version": "1.0.0",
                "description": "A test plugin for unit testing",
            }
            manifest_file = manifest_dir / "plugin.json"
            manifest_file.write_text(json.dumps(manifest))

            plugins = load_plugins_from_dirs([str(plugin_dir)])
            # The plugin should be loaded
            assert len(plugins) == 1
            assert plugins[0].name == "test-plugin"

    def test_load_plugins_deduplication(self):
        """Test that duplicate plugins are not loaded twice."""
        from openhands_cli.plugins import load_plugins_from_dirs

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create the same plugin in two locations
            for i in range(2):
                plugin_dir = Path(tmpdir) / f"location{i}" / "duplicate-plugin"
                plugin_dir.mkdir(parents=True)

                manifest_dir = plugin_dir / ".plugin"
                manifest_dir.mkdir()

                manifest = {
                    "name": "duplicate-plugin",
                    "version": "1.0.0",
                    "description": "A duplicate plugin",
                }
                manifest_file = manifest_dir / "plugin.json"
                manifest_file.write_text(json.dumps(manifest))

            # Load from both directories
            plugins = load_plugins_from_dirs(
                [
                    str(Path(tmpdir) / "location0" / "duplicate-plugin"),
                    str(Path(tmpdir) / "location1" / "duplicate-plugin"),
                ]
            )

            # Should have only one plugin (deduplication by name)
            plugin_names = [p.name for p in plugins]
            assert plugin_names.count("duplicate-plugin") == 1

    def test_load_plugins_handles_file_path(self):
        """Test that file paths (not directories) are handled gracefully."""
        from openhands_cli.plugins import load_plugins_from_dirs

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as f:
            f.write("not a directory")
            f.flush()

            plugins = load_plugins_from_dirs([f.name])
            assert plugins == []

    def test_load_plugins_from_directory_containing_plugins(self):
        """Test loading multiple plugins from a parent directory."""
        from openhands_cli.plugins import load_plugins_from_dirs

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple plugins in a parent directory
            for name in ["plugin-a", "plugin-b"]:
                plugin_dir = Path(tmpdir) / name
                plugin_dir.mkdir()

                manifest_dir = plugin_dir / ".plugin"
                manifest_dir.mkdir()

                manifest = {
                    "name": name,
                    "version": "1.0.0",
                    "description": f"Plugin {name}",
                }
                manifest_file = manifest_dir / "plugin.json"
                manifest_file.write_text(json.dumps(manifest))

            # Load all plugins from the parent directory
            plugins = load_plugins_from_dirs([tmpdir])

            # Should have loaded both plugins
            assert len(plugins) == 2
            plugin_names = {p.name for p in plugins}
            assert plugin_names == {"plugin-a", "plugin-b"}
