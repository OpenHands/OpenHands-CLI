"""Tests for loaded resources (skills, hooks, MCPs) display functionality."""

import unittest.mock as mock
from typing import cast

import pytest
from textual.containers import VerticalScroll

from openhands_cli.tui.content.resources import (
    HookInfo,
    LoadedResourcesInfo,
    MCPInfo,
    SkillInfo,
    collect_loaded_resources,
)
from openhands_cli.tui.core.commands import show_skills
from openhands_cli.tui.modals import SettingsScreen
from openhands_cli.tui.textual_app import OpenHandsApp


class TestLoadedResourcesInfo:
    """Tests for LoadedResourcesInfo dataclass."""

    def test_empty_resources(self):
        """Test LoadedResourcesInfo with no resources."""
        info = LoadedResourcesInfo()
        assert len(info.skills) == 0
        assert len(info.hooks) == 0
        assert len(info.mcps) == 0
        assert info.get_summary() == "No resources loaded"

    def test_has_resources_empty(self):
        """Test has_resources returns False when empty."""
        info = LoadedResourcesInfo()
        assert info.has_resources() is False

    def test_has_resources_with_skills(self):
        """Test has_resources returns True when skills are present."""
        info = LoadedResourcesInfo(skills=[SkillInfo(name="skill1")])
        assert info.has_resources() is True

    def test_has_resources_with_hooks(self):
        """Test has_resources returns True when hooks are present."""
        info = LoadedResourcesInfo(
            hooks=[HookInfo(hook_type="pre_tool_use", commands=["cmd1"])]
        )
        assert info.has_resources() is True

    def test_has_resources_with_mcps(self):
        """Test has_resources returns True when MCPs are present."""
        info = LoadedResourcesInfo(mcps=[MCPInfo(name="mcp1")])
        assert info.has_resources() is True

    def test_skills_only(self):
        """Test LoadedResourcesInfo with only skills."""
        info = LoadedResourcesInfo(
            skills=[
                SkillInfo(name="skill1", description="First skill"),
                SkillInfo(name="skill2", description="Second skill", source="project"),
            ]
        )
        assert len(info.skills) == 2
        assert len(info.hooks) == 0
        assert len(info.mcps) == 0
        assert "2 skills" in info.get_summary()

    def test_hooks_only(self):
        """Test LoadedResourcesInfo with only hooks."""
        info = LoadedResourcesInfo(
            hooks=[
                HookInfo(hook_type="pre_tool_use", commands=["cmd1", "cmd2"]),
                HookInfo(hook_type="post_tool_use", commands=["cmd3"]),
            ]
        )
        assert len(info.skills) == 0
        # Total hook commands: 2 + 1 = 3
        assert sum(len(h.commands) for h in info.hooks) == 3
        assert len(info.mcps) == 0
        assert "3 hooks" in info.get_summary()

    def test_mcps_only(self):
        """Test LoadedResourcesInfo with only MCPs."""
        info = LoadedResourcesInfo(
            mcps=[
                MCPInfo(name="mcp1", transport="stdio"),
                MCPInfo(name="mcp2", transport="http"),
            ]
        )
        assert len(info.skills) == 0
        assert len(info.hooks) == 0
        assert len(info.mcps) == 2
        assert "2 MCPs" in info.get_summary()

    def test_all_resources(self):
        """Test LoadedResourcesInfo with all resource types."""
        info = LoadedResourcesInfo(
            skills=[SkillInfo(name="skill1")],
            hooks=[HookInfo(hook_type="pre_tool_use", commands=["cmd1"])],
            mcps=[MCPInfo(name="mcp1", transport="stdio")],
        )
        assert len(info.skills) == 1
        assert sum(len(h.commands) for h in info.hooks) == 1
        assert len(info.mcps) == 1
        summary = info.get_summary()
        assert "1 skill" in summary
        assert "1 hook" in summary
        assert "1 MCP" in summary

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

        # Single MCP
        info_single_mcp = LoadedResourcesInfo(mcps=[MCPInfo(name="mcp1")])
        assert "1 MCP" in info_single_mcp.get_summary()
        assert "MCPs" not in info_single_mcp.get_summary()

        # Multiple MCPs
        info_multiple_mcps = LoadedResourcesInfo(
            mcps=[MCPInfo(name="mcp1"), MCPInfo(name="mcp2")]
        )
        assert "2 MCPs" in info_multiple_mcps.get_summary()

    def test_get_details(self):
        """Test get_details returns formatted string with nested bullets."""
        info = LoadedResourcesInfo(
            skills=[
                SkillInfo(name="skill1", description="First skill", source="project"),
            ],
            hooks=[HookInfo(hook_type="pre_tool_use", commands=["cmd1", "cmd2"])],
            mcps=[MCPInfo(name="mcp1", transport="stdio")],
        )
        details = info.get_details()

        # Check that details contain expected content
        assert "Skills (1):" in details
        assert "skill1" in details
        assert "First skill" in details
        assert "(project)" in details
        assert "Hooks (2):" in details
        assert "pre_tool_use: cmd1, cmd2" in details
        assert "MCPs (1):" in details
        assert "mcp1" in details
        assert "(stdio)" in details

        # Check that plain text formatting is used (no markdown)
        assert "**" not in details
        assert "*(" not in details


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
        hook = HookInfo(hook_type="pre_tool_use", commands=["cmd1", "cmd2", "cmd3"])
        assert hook.hook_type == "pre_tool_use"
        assert len(hook.commands) == 3
        assert hook.commands == ["cmd1", "cmd2", "cmd3"]

    def test_hook_info_empty_commands(self):
        """Test HookInfo with empty commands."""
        hook = HookInfo(hook_type="stop")
        assert hook.hook_type == "stop"
        assert len(hook.commands) == 0
        assert hook.commands == []


class TestMCPInfo:
    """Tests for MCPInfo dataclass."""

    def test_mcp_info_basic(self):
        """Test MCPInfo with basic attributes."""
        mcp = MCPInfo(name="test_mcp")
        assert mcp.name == "test_mcp"
        assert mcp.transport is None
        assert mcp.enabled is True

    def test_mcp_info_full(self):
        """Test MCPInfo with all attributes."""
        mcp = MCPInfo(name="test_mcp", transport="stdio", enabled=True)
        assert mcp.name == "test_mcp"
        assert mcp.transport == "stdio"
        assert mcp.enabled is True

    def test_mcp_info_http_transport(self):
        """Test MCPInfo with http transport."""
        mcp = MCPInfo(name="api_mcp", transport="http", enabled=True)
        assert mcp.name == "api_mcp"
        assert mcp.transport == "http"


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
            hooks=[HookInfo(hook_type="pre_tool_use", commands=["cmd1", "cmd2"])],
            mcps=[MCPInfo(name="mcp1", transport="stdio")],
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
        assert "mcp1" in skills_text
        assert "stdio" in skills_text

    def test_show_skills_empty_resources(self):
        """Test show_skills with empty loaded resources."""
        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        loaded_resources = LoadedResourcesInfo()

        show_skills(mock_main_display, loaded_resources)

        mock_main_display.mount.assert_called_once()
        skills_widget = mock_main_display.mount.call_args[0][0]
        skills_text = skills_widget.content

        assert "No skills, hooks, or MCPs loaded" in skills_text

    def test_show_skills_uses_plain_text_formatting(self):
        """Test that show_skills uses plain text formatting."""
        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        loaded_resources = LoadedResourcesInfo(
            skills=[SkillInfo(name="skill1")],
        )

        show_skills(mock_main_display, loaded_resources)

        skills_widget = mock_main_display.mount.call_args[0][0]
        skills_text = skills_widget.content

        # Should use plain text formatting (no markdown)
        assert "Skills (1):" in skills_text
        assert "**" not in skills_text

    def test_show_skills_with_mcps_only(self):
        """Test show_skills displays MCPs correctly."""
        mock_main_display = mock.MagicMock(spec=VerticalScroll)

        loaded_resources = LoadedResourcesInfo(
            mcps=[
                MCPInfo(name="api-server", transport="http"),
                MCPInfo(name="local-tool", transport="stdio"),
            ],
        )

        show_skills(mock_main_display, loaded_resources)

        mock_main_display.mount.assert_called_once()
        skills_widget = mock_main_display.mount.call_args[0][0]
        skills_text = skills_widget.content

        assert "MCPs (2):" in skills_text
        assert "api-server" in skills_text
        assert "http" in skills_text
        assert "local-tool" in skills_text
        assert "stdio" in skills_text


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
        assert "View loaded skills, hooks, and MCPs" in skills_command[0]

    @pytest.mark.asyncio
    async def test_skills_command_in_help(self):
        """Test that /skills is included in help text."""
        from openhands_cli.tui.core.commands import show_help

        mock_main_display = mock.MagicMock(spec=VerticalScroll)
        show_help(mock_main_display)

        help_widget = mock_main_display.mount.call_args[0][0]
        help_text = help_widget.content

        assert "/skills" in help_text
        assert "View loaded skills, hooks, and MCPs" in help_text

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

            # Set up loaded resources on ConversationContainer
            test_resources = LoadedResourcesInfo(
                skills=[SkillInfo(name="test_skill")],
            )
            oh_app.conversation_state.loaded_resources = test_resources

            # Mock show_skills to verify it's called via InputAreaContainer
            with mock.patch(
                "openhands_cli.tui.widgets.input_area.show_skills"
            ) as mock_show_skills:
                # Call the command handler on InputAreaContainer
                oh_app.conversation_state.input_area._command_skills()

                mock_show_skills.assert_called_once()
                call_args = mock_show_skills.call_args
                assert call_args[0][1] is test_resources

    @pytest.mark.asyncio
    async def test_loaded_resources_always_initialized(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """loaded_resources should be initialized on ConversationContainer."""
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda env_overrides_enabled=False: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # loaded_resources should be a LoadedResourcesInfo instance
            # on conversation_state
            assert isinstance(
                oh_app.conversation_state.loaded_resources, LoadedResourcesInfo
            )

            # Mock show_skills to verify it's called with LoadedResourcesInfo
            with mock.patch(
                "openhands_cli.tui.widgets.input_area.show_skills"
            ) as mock_show_skills:
                # Call the command handler on InputAreaContainer
                oh_app.conversation_state.input_area._command_skills()

                mock_show_skills.assert_called_once()
                call_args = mock_show_skills.call_args
                assert isinstance(call_args[0][1], LoadedResourcesInfo)


class TestCollectLoadedResources:
    """Tests for collect_loaded_resources function."""

    def test_collect_loaded_resources_no_agent(self):
        """Test collect_loaded_resources with no agent."""
        resources = collect_loaded_resources(agent=None, working_dir=None)
        assert isinstance(resources, LoadedResourcesInfo)
        # Skills should be empty without an agent
        assert resources.skills == []

    def test_collect_loaded_resources_with_skills(self):
        """Test collect_loaded_resources with skills in agent context."""
        # Create a mock agent with skills
        mock_agent = mock.MagicMock()

        mock_skill = mock.MagicMock()
        mock_skill.name = "test_skill"
        mock_skill.description = "A test skill"
        mock_skill.source = "project"

        mock_agent.agent_context = mock.MagicMock()
        mock_agent.agent_context.skills = [mock_skill]

        resources = collect_loaded_resources(agent=mock_agent, working_dir=None)

        assert isinstance(resources, LoadedResourcesInfo)
        assert len(resources.skills) == 1
        assert resources.skills[0].name == "test_skill"
        assert resources.skills[0].description == "A test skill"
        assert resources.skills[0].source == "project"
