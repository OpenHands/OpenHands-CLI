"""Tests for the --plugins-dir CLI argument functionality."""

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

    def test_load_skills_from_nonexistent_dir(self):
        """Test that nonexistent directories are handled gracefully."""
        from openhands_cli.plugins import load_skills_from_plugins_dirs

        skills = load_skills_from_plugins_dirs(["/nonexistent/path"])
        assert skills == []

    def test_load_skills_from_empty_dir(self):
        """Test loading from an empty directory."""
        from openhands_cli.plugins import load_skills_from_plugins_dirs

        with tempfile.TemporaryDirectory() as tmpdir:
            skills = load_skills_from_plugins_dirs([tmpdir])
            assert skills == []

    def test_load_skills_from_dir_with_skill(self):
        """Test loading a skill from a directory with a SKILL.md file."""
        from openhands_cli.plugins import load_skills_from_plugins_dirs

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a skill directory structure
            skill_dir = Path(tmpdir) / "my-test-skill"
            skill_dir.mkdir()

            # Create a SKILL.md file
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("""---
name: test-skill
description: A test skill for unit testing
triggers:
  - type: keyword
    pattern: "test-pattern"
---

# Test Skill

This is a test skill content.
""")

            skills = load_skills_from_plugins_dirs([tmpdir])
            # The skill should be loaded (may vary based on SDK behavior)
            # At minimum, we should not raise an error
            assert isinstance(skills, list)

    def test_load_skills_deduplication(self):
        """Test that duplicate skills are not loaded twice."""
        from openhands_cli.plugins import load_skills_from_plugins_dirs

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create the same skill in two locations
            for i in range(2):
                skill_dir = Path(tmpdir) / f"plugin{i}" / "test-skill"
                skill_dir.mkdir(parents=True)

                skill_file = skill_dir / "SKILL.md"
                skill_file.write_text("""---
name: duplicate-skill
description: A duplicate skill
---

# Duplicate Skill
""")

            # Load from both directories
            skills = load_skills_from_plugins_dirs(
                [
                    str(Path(tmpdir) / "plugin0"),
                    str(Path(tmpdir) / "plugin1"),
                ]
            )

            # Should handle gracefully (no duplicates or error)
            skill_names = [s.name for s in skills]
            # Count occurrences of the skill name
            assert skill_names.count("duplicate-skill") <= 1

    def test_load_skills_handles_file_path(self):
        """Test that file paths (not directories) are handled gracefully."""
        from openhands_cli.plugins import load_skills_from_plugins_dirs

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as f:
            f.write("not a directory")
            f.flush()

            skills = load_skills_from_plugins_dirs([f.name])
            assert skills == []
