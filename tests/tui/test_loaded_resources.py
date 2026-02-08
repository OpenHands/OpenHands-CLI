"""Tests for loaded resources (skills, hooks, tools) display functionality."""

import unittest.mock as mock
from typing import cast

import pytest
from textual.containers import VerticalScroll

from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.content.resources import (
    HookInfo,
    LoadedResourcesInfo,
    SkillInfo,
    ToolInfo,
)
from openhands_cli.tui.core.commands import show_skills
from openhands_cli.tui.modals import SettingsScreen
from openhands_cli.tui.textual_app import OpenHandsApp


class TestLoadedResourcesInfo:
    """Tests for LoadedResourcesInfo dataclass."""

    def test_empty_resources(self):
        """Test LoadedResourcesInfo with no resources."""
        info = LoadedResourcesInfo()
        assert info.skills_count == 0
        assert info.hooks_count == 0
        assert info.tools_count == 0
        assert info.get_summary() == "No resources loaded"

    def test_skills_only(self):
        """Test LoadedResourcesInfo with only skills."""
        info = LoadedResourcesInfo(
            skills=[
                SkillInfo(name="skill1", description="First skill"),
                SkillInfo(name="skill2", description="Second skill", source="project"),
            ]
        )
        assert info.skills_count == 2
        assert info.hooks_count == 0
        assert info.tools_count == 0
        assert "2 skills" in info.get_summary()

    def test_hooks_only(self):
        """Test LoadedResourcesInfo with only hooks."""
        info = LoadedResourcesInfo(
            hooks=[
                HookInfo(hook_type="pre_tool_use", count=2),
                HookInfo(hook_type="post_tool_use", count=1),
            ]
        )
        assert info.skills_count == 0
        assert info.hooks_count == 3  # Sum of all hook counts
        assert info.tools_count == 0
        assert "3 hooks" in info.get_summary()

    def test_tools_only(self):
        """Test LoadedResourcesInfo with only tools."""
        info = LoadedResourcesInfo(
            tools=[
                ToolInfo(name="tool1", description="First tool"),
                ToolInfo(name="tool2"),
            ]
        )
        assert info.skills_count == 0
        assert info.hooks_count == 0
        assert info.tools_count == 2
        assert "2 tools" in info.get_summary()

    def test_all_resources(self):
        """Test LoadedResourcesInfo with all resource types."""
        info = LoadedResourcesInfo(
            skills=[SkillInfo(name="skill1")],
            hooks=[HookInfo(hook_type="pre_tool_use", count=1)],
            tools=[ToolInfo(name="tool1"), ToolInfo(name="tool2")],
        )
        assert info.skills_count == 1
        assert info.hooks_count == 1
        assert info.tools_count == 2
        summary = info.get_summary()
        assert "1 skill" in summary
        assert "1 hook" in summary
        assert "2 tools" in summary

    def test_singular_plural(self):
        """Test that singular/plural forms are correct."""
        # Single skill
        info_single = LoadedResourcesInfo(skills=[SkillInfo(name="skill1")])
        assert "1 skill" in info_single.get_summary()
        assert "skills" not in info_single.get_summary()

        # Multiple skills
        info_multiple = LoadedResourcesInfo(
            skills=[SkillInfo(name="skill1"), SkillInfo(name="skill2")]
        )
        assert "2 skills" in info_multiple.get_summary()

    def test_get_details(self):
        """Test get_details returns formatted string with theme colors."""
        info = LoadedResourcesInfo(
            skills=[
                SkillInfo(name="skill1", description="First skill", source="project"),
            ],
            hooks=[HookInfo(hook_type="pre_tool_use", count=2)],
            tools=[ToolInfo(name="tool1", description="First tool")],
        )
        details = info.get_details(theme=OPENHANDS_THEME)

        # Check that details contain expected content
        assert "Skills (1):" in details
        assert "skill1" in details
        assert "First skill" in details
        assert "project" in details
        assert "Hooks (2):" in details
        assert "pre_tool_use: 2" in details
        assert "Tools (1):" in details
        assert "tool1" in details
        assert "First tool" in details

        # Check that theme colors are used
        assert OPENHANDS_THEME.primary in details


class TestSkillInfo:
    """Tests for SkillInfo dataclass."""

    def test_skill_info_basic(self):
        """Test SkillInfo with basic attributes."""
        skill = SkillInfo(name="test_skill")
        assert skill.name == "test_skill"
        assert skill.description is None
        assert skill.source is None

    def test_skill_info_full(self):
        """Test SkillInfo with all attributes."""
        skill = SkillInfo(
            name="test_skill",
            description="A test skill",
            source="project/.openhands/skills",
        )
        assert skill.name == "test_skill"
        assert skill.description == "A test skill"
        assert skill.source == "project/.openhands/skills"


class TestHookInfo:
    """Tests for HookInfo dataclass."""

    def test_hook_info(self):
        """Test HookInfo dataclass."""
        hook = HookInfo(hook_type="pre_tool_use", count=3)
        assert hook.hook_type == "pre_tool_use"
        assert hook.count == 3


class TestToolInfo:
    """Tests for ToolInfo dataclass."""

    def test_tool_info_basic(self):
        """Test ToolInfo with basic attributes."""
        tool = ToolInfo(name="test_tool")
        assert tool.name == "test_tool"
        assert tool.description is None

    def test_tool_info_full(self):
        """Test ToolInfo with all attributes."""
        tool = ToolInfo(name="test_tool", description="A test tool")
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"


class TestShowSkillsCommand:
    """Tests for show_skills command function."""

    def test_show_skills_with_resources(self):
        """Test show_skills displays loaded resources."""
        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        loaded_resources = LoadedResourcesInfo(
            skills=[
                SkillInfo(name="skill1", description="First skill"),
                SkillInfo(name="skill2", source="project"),
            ],
            hooks=[HookInfo(hook_type="pre_tool_use", count=2)],
            tools=[ToolInfo(name="tool1", description="First tool")],
        )

        show_skills(mock_main_display, loaded_resources)

        # Verify mount was called
        mock_main_display.mount.assert_called_once()
        skills_widget = mock_main_display.mount.call_args[0][0]
        skills_text = skills_widget.content

        # Check content
        assert "Loaded Resources" in skills_text
        assert "skill1" in skills_text
        assert "skill2" in skills_text
        assert "pre_tool_use" in skills_text
        assert "tool1" in skills_text

    def test_show_skills_without_resources(self):
        """Test show_skills with None loaded resources."""
        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        show_skills(mock_main_display, None)

        mock_main_display.mount.assert_called_once()
        skills_widget = mock_main_display.mount.call_args[0][0]
        skills_text = skills_widget.content

        assert "No resources information available" in skills_text

    def test_show_skills_empty_resources(self):
        """Test show_skills with empty loaded resources."""
        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        loaded_resources = LoadedResourcesInfo()

        show_skills(mock_main_display, loaded_resources)

        mock_main_display.mount.assert_called_once()
        skills_widget = mock_main_display.mount.call_args[0][0]
        skills_text = skills_widget.content

        assert "No skills, hooks, or tools loaded" in skills_text

    def test_show_skills_uses_theme_colors(self):
        """Test that show_skills uses OpenHands theme colors."""
        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        loaded_resources = LoadedResourcesInfo(
            skills=[SkillInfo(name="skill1")],
        )

        show_skills(mock_main_display, loaded_resources)

        skills_widget = mock_main_display.mount.call_args[0][0]
        skills_text = skills_widget.content

        # Should use OpenHands theme colors
        assert OPENHANDS_THEME.primary in skills_text


class TestSkillsCommandInApp:
    """Integration tests for /skills command in OpenHandsApp."""

    @pytest.mark.asyncio
    async def test_skills_command_is_valid(self):
        """Test that /skills is a valid command."""
        from openhands_cli.tui.core.commands import is_valid_command

        assert is_valid_command("/skills") is True

    @pytest.mark.asyncio
    async def test_skills_command_in_commands_list(self):
        """Test that /skills is in the COMMANDS list."""
        from openhands_cli.tui.core.commands import COMMANDS

        command_strings = [str(cmd.main) for cmd in COMMANDS]
        skills_command = [cmd for cmd in command_strings if cmd.startswith("/skills")]
        assert len(skills_command) == 1
        assert "View loaded skills, hooks, and tools" in skills_command[0]

    @pytest.mark.asyncio
    async def test_skills_command_in_help(self):
        """Test that /skills is included in help text."""
        from openhands_cli.tui.core.commands import show_help

        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        show_help(mock_main_display)

        help_widget = mock_main_display.mount.call_args[0][0]
        help_text = help_widget.content

        assert "/skills" in help_text
        assert "View loaded skills, hooks, and tools" in help_text

    @pytest.mark.asyncio
    async def test_skills_command_handler(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """/skills command should display loaded resources."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Set up loaded resources
            oh_app._loaded_resources = LoadedResourcesInfo(
                skills=[SkillInfo(name="test_skill")],
                tools=[ToolInfo(name="test_tool")],
            )

            # Mock show_skills to verify it's called via InputAreaContainer
            with mock.patch(
                "openhands_cli.tui.widgets.input_area.show_skills"
            ) as mock_show_skills:
                # Call the command handler on InputAreaContainer
                oh_app.conversation_state.input_area._command_skills()

                mock_show_skills.assert_called_once()
                call_args = mock_show_skills.call_args
                assert call_args[0][1] is oh_app._loaded_resources

    @pytest.mark.asyncio
    async def test_skills_command_without_loaded_resources(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """/skills command should handle missing loaded resources gracefully."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Explicitly set _loaded_resources to None to test the fallback
            oh_app._loaded_resources = None  # type: ignore

            # Mock show_skills to verify it's called with None via InputAreaContainer
            with mock.patch(
                "openhands_cli.tui.widgets.input_area.show_skills"
            ) as mock_show_skills:
                # Call the command handler on InputAreaContainer
                oh_app.conversation_state.input_area._command_skills()

                mock_show_skills.assert_called_once()
                call_args = mock_show_skills.call_args
                assert call_args[0][1] is None
