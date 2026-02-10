"""Tests for loaded resources (skills, hooks, tools, MCPs) display functionality."""

import unittest.mock as mock
from typing import cast

import pytest
from textual.containers import VerticalScroll

from openhands_cli.tui.content.resources import (
    HookInfo,
    LoadedResourcesInfo,
    MCPInfo,
    SkillInfo,
    ToolInfo,
    _extract_skills_from_system_prompt,
    _is_mcp_tool,
    collect_loaded_resources,
    collect_resources_from_system_prompt,
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
        assert info.mcps_count == 0
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
        info = LoadedResourcesInfo(hooks=[HookInfo(hook_type="pre_tool_use", count=1)])
        assert info.has_resources() is True

    def test_has_resources_with_tools(self):
        """Test has_resources returns True when tools are present."""
        info = LoadedResourcesInfo(tools=[ToolInfo(name="tool1")])
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
        assert info.skills_count == 2
        assert info.hooks_count == 0
        assert info.tools_count == 0
        assert info.mcps_count == 0
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
        assert info.mcps_count == 0
        assert "3 hooks" in info.get_summary()

    def test_tools_only(self):
        """Test LoadedResourcesInfo with only tools."""
        info = LoadedResourcesInfo(
            tools=[
                ToolInfo(name="tool1"),
                ToolInfo(name="tool2"),
            ]
        )
        assert info.skills_count == 0
        assert info.hooks_count == 0
        assert info.tools_count == 2
        assert info.mcps_count == 0
        assert "2 tools" in info.get_summary()

    def test_mcps_only(self):
        """Test LoadedResourcesInfo with only MCPs."""
        info = LoadedResourcesInfo(
            mcps=[
                MCPInfo(name="mcp1", transport="stdio"),
                MCPInfo(name="mcp2", transport="http"),
            ]
        )
        assert info.skills_count == 0
        assert info.hooks_count == 0
        assert info.tools_count == 0
        assert info.mcps_count == 2
        assert "2 MCPs" in info.get_summary()

    def test_all_resources(self):
        """Test LoadedResourcesInfo with all resource types."""
        info = LoadedResourcesInfo(
            skills=[SkillInfo(name="skill1")],
            hooks=[HookInfo(hook_type="pre_tool_use", count=1)],
            tools=[ToolInfo(name="tool1"), ToolInfo(name="tool2")],
            mcps=[MCPInfo(name="mcp1", transport="stdio")],
        )
        assert info.skills_count == 1
        assert info.hooks_count == 1
        assert info.tools_count == 2
        assert info.mcps_count == 1
        summary = info.get_summary()
        assert "1 skill" in summary
        assert "1 hook" in summary
        assert "2 tools" in summary
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
            hooks=[HookInfo(hook_type="pre_tool_use", count=2)],
            tools=[ToolInfo(name="tool1")],
            mcps=[MCPInfo(name="mcp1", transport="stdio")],
        )
        details = info.get_details()

        # Check that details contain expected content
        assert "Skills (1):" in details
        assert "skill1" in details
        assert "First skill" in details
        assert "(project)" in details
        assert "Hooks (2):" in details
        assert "pre_tool_use: 2" in details
        assert "Tools (1):" in details
        assert "tool1" in details
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
        hook = HookInfo(hook_type="pre_tool_use", count=3)
        assert hook.hook_type == "pre_tool_use"
        assert hook.count == 3


class TestToolInfo:
    """Tests for ToolInfo dataclass."""

    def test_tool_info_basic(self):
        """Test ToolInfo with basic attributes."""
        tool = ToolInfo(name="test_tool")
        assert tool.name == "test_tool"


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
            hooks=[HookInfo(hook_type="pre_tool_use", count=2)],
            tools=[ToolInfo(name="tool1")],
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
        assert "tool1" in skills_text
        assert "mcp1" in skills_text
        assert "stdio" in skills_text

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

        assert "No skills, hooks, tools, or MCPs loaded" in skills_text

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


class TestCollectLoadedResources:
    """Tests for collect_loaded_resources function."""

    def test_collect_loaded_resources_no_agent(self):
        """Test collect_loaded_resources with no agent."""
        resources = collect_loaded_resources(agent=None, working_dir=None)
        assert isinstance(resources, LoadedResourcesInfo)
        # Skills and tools should be empty without an agent
        assert resources.skills == []
        assert resources.tools == []

    def test_collect_loaded_resources_with_mock_agent(self):
        """Test collect_loaded_resources with a mock agent."""
        # Create a mock agent with tools
        mock_agent = mock.MagicMock()
        mock_agent.agent_context = None

        # Create mock tools
        mock_tool1 = mock.MagicMock()
        mock_tool1.name = "terminal"
        mock_tool2 = mock.MagicMock()
        mock_tool2.name = "file_editor"
        mock_agent.tools = [mock_tool1, mock_tool2]

        resources = collect_loaded_resources(agent=mock_agent, working_dir=None)

        assert isinstance(resources, LoadedResourcesInfo)
        assert len(resources.tools) == 2
        assert resources.tools[0].name == "terminal"
        assert resources.tools[1].name == "file_editor"

    def test_collect_loaded_resources_with_skills(self):
        """Test collect_loaded_resources with skills in agent context."""
        # Create a mock agent with skills
        mock_agent = mock.MagicMock()
        mock_agent.tools = []

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


class TestCollectResourcesFromSystemPrompt:
    """Tests for collect_resources_from_system_prompt function."""

    def test_collect_resources_with_tools(self):
        """Test extracting tools from SystemPromptEvent."""
        from openhands.sdk.llm import TextContent

        # Create mock SystemPromptEvent
        mock_event = mock.MagicMock()
        mock_event.system_prompt = TextContent(text="Test system prompt")

        # Create mock tools
        mock_tool1 = mock.MagicMock()
        mock_tool1.name = "terminal"
        mock_tool1.description = "Execute bash commands"
        mock_tool1.meta = None

        mock_tool2 = mock.MagicMock()
        mock_tool2.name = "file_editor"
        mock_tool2.description = "Edit files"
        mock_tool2.meta = None

        mock_event.tools = [mock_tool1, mock_tool2]

        # Mock _is_mcp_tool to return False for regular tools
        with mock.patch(
            "openhands_cli.tui.content.resources._is_mcp_tool", return_value=False
        ):
            resources = collect_resources_from_system_prompt(
                event=mock_event, working_dir=None
            )

        assert isinstance(resources, LoadedResourcesInfo)
        assert len(resources.tools) == 2
        assert resources.tools[0].name == "terminal"
        assert resources.tools[1].name == "file_editor"

    def test_collect_resources_with_mcp_tools(self):
        """Test extracting MCP tools from SystemPromptEvent."""
        from openhands.sdk.llm import TextContent

        # Create mock SystemPromptEvent
        mock_event = mock.MagicMock()
        mock_event.system_prompt = TextContent(text="Test system prompt")

        # Create mock MCP tool
        mock_mcp_tool = mock.MagicMock()
        mock_mcp_tool.name = "mcp_search"
        mock_mcp_tool.description = "Search using MCP"
        mock_mcp_tool.meta = {"mcp_server": "search-server"}

        mock_event.tools = [mock_mcp_tool]

        # Mock _is_mcp_tool to return True for MCP tools
        with mock.patch(
            "openhands_cli.tui.content.resources._is_mcp_tool", return_value=True
        ):
            resources = collect_resources_from_system_prompt(
                event=mock_event, working_dir=None
            )

        assert isinstance(resources, LoadedResourcesInfo)
        assert len(resources.tools) == 1
        assert resources.tools[0].name == "mcp_search"
        assert len(resources.mcps) == 1
        assert resources.mcps[0].name == "search-server"

    def test_collect_resources_with_skills_in_prompt(self):
        """Test extracting skills from system prompt text."""
        from openhands.sdk.llm import TextContent

        system_prompt_text = """
You are an AI assistant.

<available_skills>
- code_review: Review code for best practices
- testing: Write unit tests for code
</available_skills>

Please help the user.
"""
        mock_event = mock.MagicMock()
        mock_event.system_prompt = TextContent(text=system_prompt_text)
        mock_event.tools = []

        resources = collect_resources_from_system_prompt(
            event=mock_event, working_dir=None
        )

        assert isinstance(resources, LoadedResourcesInfo)
        assert len(resources.skills) == 2
        assert resources.skills[0].name == "code_review"
        assert resources.skills[0].description == "Review code for best practices"
        assert resources.skills[1].name == "testing"
        assert resources.skills[1].description == "Write unit tests for code"


class TestExtractSkillsFromSystemPrompt:
    """Tests for _extract_skills_from_system_prompt function."""

    def test_extract_skills_with_available_skills_section(self):
        """Test extracting skills from available_skills section."""
        system_prompt = """
<available_skills>
- skill1: Description of skill 1
- skill2: Description of skill 2
</available_skills>
"""
        skills = _extract_skills_from_system_prompt(system_prompt)
        assert len(skills) == 2
        assert skills[0].name == "skill1"
        assert skills[0].description == "Description of skill 1"
        assert skills[1].name == "skill2"
        assert skills[1].description == "Description of skill 2"

    def test_extract_skills_no_skills_section(self):
        """Test extracting skills when no available_skills section exists."""
        system_prompt = "You are an AI assistant. Help the user."
        skills = _extract_skills_from_system_prompt(system_prompt)
        assert len(skills) == 0

    def test_extract_skills_empty_section(self):
        """Test extracting skills from empty available_skills section."""
        system_prompt = """
<available_skills>
</available_skills>
"""
        skills = _extract_skills_from_system_prompt(system_prompt)
        assert len(skills) == 0


class TestIsMcpTool:
    """Tests for _is_mcp_tool function."""

    def test_is_mcp_tool_with_regular_tool(self):
        """Test _is_mcp_tool returns False for regular tools."""
        mock_tool = mock.MagicMock()
        # Regular tool should return False
        result = _is_mcp_tool(mock_tool)
        assert result is False

    def test_is_mcp_tool_with_mcp_tool(self):
        """Test _is_mcp_tool returns True for MCPToolDefinition."""
        from openhands.sdk.mcp.tool import MCPToolDefinition

        # Create a mock that is an instance of MCPToolDefinition
        mock_tool = mock.MagicMock(spec=MCPToolDefinition)
        result = _is_mcp_tool(mock_tool)
        assert result is True
