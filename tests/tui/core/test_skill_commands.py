"""Tests for /skill lifecycle commands."""

from unittest import mock

import pytest
from textual.containers import VerticalScroll

from openhands.sdk.skills import (
    disable_skill,
    enable_skill,
    install_skill,
    list_installed_skills,
    uninstall_skill,
)
from openhands_cli.tui.core.commands import is_valid_command
from openhands_cli.tui.core.skill_commands import handle_skill_command
from openhands_cli.tui.widgets.user_input.input_field import InputField


_SDK = "openhands.sdk.skills"


class TestIsValidCommandWithSkill:
    """Test is_valid_command supports /skill prefix matching."""

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("/skill", True),
            ("/skill install foo", True),
            ("/skill list", True),
            ("/skill enable bar", True),
            ("/skill disable bar", True),
            ("/skill uninstall bar", True),
            ("/skill update bar", True),
            ("/skills", True),
            ("/skillz", False),
            ("/skill_bad", False),
        ],
    )
    def test_skill_prefix_matching(self, cmd, expected):
        assert is_valid_command(cmd) is expected


class TestParseCommand:
    """Test InputField._parse_command splits command and args."""

    @pytest.mark.parametrize(
        "content,expected",
        [
            ("/help", ("help", "")),
            ("/skill install foo", ("skill", "install foo")),
            ("/skill list", ("skill", "list")),
            ("/skill", ("skill", "")),
        ],
    )
    def test_parse_command(self, content, expected):
        assert InputField._parse_command(content) == expected


class TestHandleSkillCommand:
    """Test handle_skill_command routing and output."""

    def _call(self, args: str) -> str:
        sv = mock.MagicMock(spec=VerticalScroll)
        handle_skill_command(sv, args)
        sv.mount.assert_called_once()
        return sv.mount.call_args[0][0].content

    def test_no_subcommand_shows_help(self):
        text = self._call("")
        assert "Skill Management" in text

    def test_unknown_subcommand_shows_help(self):
        text = self._call("bogus")
        assert "Skill Management" in text

    def test_install_missing_source(self):
        text = self._call("install")
        assert "Usage" in text

    @mock.patch(f"{_SDK}.install_skill")
    def test_install_success(self, mock_fn):
        mock_fn.return_value = mock.Mock(name="my-skill")
        text = self._call("install https://example.com/skill")
        mock_fn.assert_called_once_with("https://example.com/skill")
        assert "Installed" in text

    @mock.patch(
        f"{_SDK}.install_skill",
        side_effect=RuntimeError("fail"),
    )
    def test_install_error(self, _):
        text = self._call("install bad-source")
        assert "Install failed" in text

    @mock.patch(f"{_SDK}.list_installed_skills", return_value=[])
    def test_list_empty(self, _):
        text = self._call("list")
        assert "No installed skills" in text

    @mock.patch(f"{_SDK}.list_installed_skills")
    def test_list_with_skills(self, mock_fn):
        mock_fn.return_value = [
            mock.Mock(name="a", enabled=True, description="desc-a"),
            mock.Mock(name="b", enabled=False, description=""),
        ]
        text = self._call("list")
        assert "Installed Skills (2)" in text
        assert "enabled" in text
        assert "disabled" in text

    def test_enable_missing_name(self):
        text = self._call("enable")
        assert "Usage" in text

    @mock.patch(f"{_SDK}.enable_skill", return_value=True)
    def test_enable_success(self, mock_fn):
        text = self._call("enable my-skill")
        mock_fn.assert_called_once_with("my-skill")
        assert "Enabled" in text

    @mock.patch(f"{_SDK}.enable_skill", return_value=False)
    def test_enable_not_found(self, _):
        text = self._call("enable missing")
        assert "not found" in text

    def test_disable_missing_name(self):
        text = self._call("disable")
        assert "Usage" in text

    @mock.patch(f"{_SDK}.disable_skill", return_value=True)
    def test_disable_success(self, mock_fn):
        text = self._call("disable my-skill")
        mock_fn.assert_called_once_with("my-skill")
        assert "Disabled" in text

    @mock.patch(f"{_SDK}.disable_skill", return_value=False)
    def test_disable_not_found(self, _):
        text = self._call("disable missing")
        assert "not found" in text

    def test_uninstall_missing_name(self):
        text = self._call("uninstall")
        assert "Usage" in text

    @mock.patch(f"{_SDK}.uninstall_skill", return_value=True)
    def test_uninstall_success(self, mock_fn):
        text = self._call("uninstall my-skill")
        mock_fn.assert_called_once_with("my-skill")
        assert "Uninstalled" in text

    @mock.patch(f"{_SDK}.uninstall_skill", return_value=False)
    def test_uninstall_not_found(self, _):
        text = self._call("uninstall missing")
        assert "not found" in text

    def test_update_missing_name(self):
        text = self._call("update")
        assert "Usage" in text

    @mock.patch(f"{_SDK}.update_skill")
    def test_update_success(self, mock_fn):
        mock_fn.return_value = mock.Mock(name="my-skill")
        text = self._call("update my-skill")
        mock_fn.assert_called_once_with("my-skill")
        assert "Updated" in text

    @mock.patch(f"{_SDK}.update_skill", return_value=None)
    def test_update_not_found(self, _):
        text = self._call("update missing")
        assert "not found" in text

    # -- SDK exception handling for each subcommand --

    @mock.patch(f"{_SDK}.list_installed_skills", side_effect=RuntimeError("boom"))
    def test_list_error(self, _):
        text = self._call("list")
        assert "Error" in text

    @mock.patch(f"{_SDK}.enable_skill", side_effect=RuntimeError("boom"))
    def test_enable_error(self, _):
        text = self._call("enable my-skill")
        assert "Error" in text

    @mock.patch(f"{_SDK}.disable_skill", side_effect=RuntimeError("boom"))
    def test_disable_error(self, _):
        text = self._call("disable my-skill")
        assert "Error" in text

    @mock.patch(f"{_SDK}.uninstall_skill", side_effect=RuntimeError("boom"))
    def test_uninstall_error(self, _):
        text = self._call("uninstall my-skill")
        assert "Error" in text

    @mock.patch(f"{_SDK}.update_skill", side_effect=RuntimeError("boom"))
    def test_update_error(self, _):
        text = self._call("update my-skill")
        assert "Error" in text


class TestSkillLifecycleIntegration:
    """End-to-end lifecycle test using real SDK calls with a temp directory."""

    def test_full_lifecycle(self, tmp_path):
        installed_dir = tmp_path / "installed"
        installed_dir.mkdir()

        # Create a local skill
        skill_dir = tmp_path / "test-lifecycle"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-lifecycle\ndescription: A test skill\n---\n# Test"
        )

        # Install
        info = install_skill(str(skill_dir), installed_dir=installed_dir)
        assert info.name == "test-lifecycle"

        # List — should show enabled
        skills = list_installed_skills(installed_dir=installed_dir)
        assert len(skills) == 1
        assert skills[0].name == "test-lifecycle"
        assert skills[0].enabled is True

        # Disable
        assert disable_skill("test-lifecycle", installed_dir=installed_dir) is True
        skills = list_installed_skills(installed_dir=installed_dir)
        assert skills[0].enabled is False

        # Re-enable without reinstalling
        assert enable_skill("test-lifecycle", installed_dir=installed_dir) is True
        skills = list_installed_skills(installed_dir=installed_dir)
        assert skills[0].enabled is True

        # Uninstall
        assert uninstall_skill("test-lifecycle", installed_dir=installed_dir) is True
        assert list_installed_skills(installed_dir=installed_dir) == []
        assert not (installed_dir / "test-lifecycle").exists()

    def test_load_user_skills_sees_installed_skill(self, tmp_path):
        """Regression: install_skill() + load_user_skills() must find the skill.

        Verifies the end-to-end data path that was broken before SDK v1.18.1:
        installed skills are written to installed/ and load_user_skills() must
        include them.
        """
        installed_dir = tmp_path / "installed"
        installed_dir.mkdir()

        # Create and install a skill
        skill_dir = tmp_path / "loader-test"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: loader-test\ndescription: Verify loader\n---\n# Test"
        )
        install_skill(str(skill_dir), installed_dir=installed_dir)

        from openhands.sdk.skills import load_user_skills

        with (
            mock.patch(
                "openhands.sdk.skills.skill.USER_SKILLS_DIRS", [tmp_path / "empty"]
            ),
            mock.patch(
                "openhands.sdk.skills.installed.DEFAULT_INSTALLED_SKILLS_DIR",
                installed_dir,
            ),
        ):
            loaded = load_user_skills()

        names = [s.name for s in loaded]
        assert "loader-test" in names
