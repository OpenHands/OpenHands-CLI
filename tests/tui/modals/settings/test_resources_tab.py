"""Tests for ResourcesTab component."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from openhands_cli.tui.modals.settings.components.resources_tab import ResourcesTab


def _create_mock_agent(
    skills: list[Any] | None = None,
    tools: list[Any] | None = None,
    mcp_config: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock Agent with configurable skills, tools, and MCP config."""
    mock_agent = MagicMock()

    # Set up agent_context with skills
    if skills is not None:
        mock_agent.agent_context = MagicMock()
        mock_agent.agent_context.skills = skills
    else:
        mock_agent.agent_context = None

    # Set up tools
    mock_agent.tools = tools or []

    # Set up MCP config
    mock_agent.mcp_config = mcp_config or {"mcpServers": {}}

    return mock_agent


def _create_mock_skill(
    name: str, description: str | None = None, source: str | None = None
) -> MagicMock:
    """Create a mock skill."""
    skill = MagicMock()
    skill.name = name
    skill.description = description
    skill.source = source
    return skill


def _create_mock_tool(name: str) -> MagicMock:
    """Create a mock tool."""
    tool = MagicMock()
    tool.name = name
    return tool


class _TestApp(App):
    """Small Textual app to mount the tab under test."""

    def __init__(self, mock_agent: MagicMock | None = None, mock_hook_config=None):
        super().__init__()
        self.mock_agent = mock_agent
        self.mock_hook_config = mock_hook_config

    def compose(self) -> ComposeResult:
        with patch(
            "openhands_cli.tui.modals.settings.components.resources_tab.AgentStore"
        ) as mock_store_class:
            mock_store = MagicMock()
            mock_store.load_from_disk.return_value = self.mock_agent
            mock_store_class.return_value = mock_store

            with patch(
                "openhands_cli.tui.modals.settings.components.resources_tab.HookConfig"
            ) as mock_hook_class:
                mock_hook_class.load.return_value = self.mock_hook_config
                yield ResourcesTab()


class TestResourcesTab:
    """Tests for ResourcesTab component."""

    @pytest.mark.asyncio
    async def test_compose_renders_section_headers(self):
        """Verify all section headers are rendered."""
        app = _TestApp()

        async with app.run_test():
            tab = app.query_one(ResourcesTab)

            # Check for section headers
            headers = tab.query(".resources_section_header")
            header_texts = [str(h.render()) for h in headers]

            assert "Skills" in header_texts
            assert "Hooks" in header_texts
            assert "MCP Servers" in header_texts

    @pytest.mark.asyncio
    async def test_skills_section_shows_no_skills_when_empty(self):
        """Verify skills section shows 'No skills loaded' when empty."""
        mock_agent = _create_mock_agent(skills=[])
        app = _TestApp(mock_agent=mock_agent)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            skills_content = tab.query_one("#skills_content", Static)

            # The content should indicate no skills
            content = str(skills_content.render())
            assert "No skills loaded" in content

    @pytest.mark.asyncio
    async def test_skills_section_shows_skills_when_present(self):
        """Verify skills section shows skill names when present."""
        skills = [
            _create_mock_skill("test_skill", "A test skill", "local"),
            _create_mock_skill("another_skill", "Another skill"),
        ]
        mock_agent = _create_mock_agent(skills=skills)
        app = _TestApp(mock_agent=mock_agent)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            skills_content = tab.query_one("#skills_content", Static)

            content = str(skills_content.render())
            assert "test_skill" in content
            assert "another_skill" in content

    @pytest.mark.asyncio
    async def test_hooks_section_shows_no_hooks_when_empty(self):
        """Verify hooks section shows 'No hooks loaded' when empty."""
        mock_hook_config = MagicMock()
        mock_hook_config.pre_tool_use = []
        mock_hook_config.post_tool_use = []
        mock_hook_config.user_prompt_submit = []
        mock_hook_config.session_start = []
        mock_hook_config.session_end = []
        mock_hook_config.stop = []

        app = _TestApp(mock_hook_config=mock_hook_config)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            hooks_content = tab.query_one("#hooks_content", Static)

            content = str(hooks_content.render())
            assert "No hooks loaded" in content

    @pytest.mark.asyncio
    async def test_hooks_section_shows_hooks_when_present(self):
        """Verify hooks section shows hook types and commands when present."""
        # Create mock hook definitions with commands
        mock_hook_def1 = MagicMock()
        mock_hook_def1.command = "cmd1"
        mock_hook_def2 = MagicMock()
        mock_hook_def2.command = "cmd2"
        mock_hook_def3 = MagicMock()
        mock_hook_def3.command = "cmd3"

        # Create mock matchers with hooks
        mock_matcher1 = MagicMock()
        mock_matcher1.hooks = [mock_hook_def1, mock_hook_def2]
        mock_matcher2 = MagicMock()
        mock_matcher2.hooks = [mock_hook_def3]

        mock_hook_config = MagicMock()
        mock_hook_config.pre_tool_use = [mock_matcher1]  # 2 hook commands
        mock_hook_config.post_tool_use = [mock_matcher2]  # 1 hook command
        mock_hook_config.user_prompt_submit = []
        mock_hook_config.session_start = []
        mock_hook_config.session_end = []
        mock_hook_config.stop = []

        app = _TestApp(mock_hook_config=mock_hook_config)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            hooks_content = tab.query_one("#hooks_content", Static)

            content = str(hooks_content.render())
            assert "pre_tool_use" in content
            assert "post_tool_use" in content
            assert "cmd1" in content
            assert "cmd2" in content
            assert "cmd3" in content

    @pytest.mark.asyncio
    async def test_mcp_section_shows_no_servers_when_empty(self):
        """Verify MCP section shows 'No MCP servers configured' when empty."""
        mock_agent = _create_mock_agent(mcp_config={"mcpServers": {}})
        app = _TestApp(mock_agent=mock_agent)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            mcp_content = tab.query_one("#mcp_content", Static)

            content = str(mcp_content.render())
            assert "No MCP servers configured" in content

    @pytest.mark.asyncio
    async def test_mcp_section_shows_servers_when_present(self):
        """Verify MCP section shows server names when present."""
        mcp_config = {
            "mcpServers": {
                "test_server": {"url": "https://example.com", "transport": "http"},
                "another_server": {"command": "python", "args": ["-m", "server"]},
            }
        }
        mock_agent = _create_mock_agent(mcp_config=mcp_config)
        app = _TestApp(mock_agent=mock_agent)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            mcp_content = tab.query_one("#mcp_content", Static)

            content = str(mcp_content.render())
            assert "test_server" in content
            assert "another_server" in content

    @pytest.mark.asyncio
    async def test_handles_agent_load_failure(self):
        """Verify tab handles agent load failure gracefully."""
        app = _TestApp(mock_agent=None)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            skills_content = tab.query_one("#skills_content", Static)
            mcp_content = tab.query_one("#mcp_content", Static)

            # Should show error messages
            skills_text = str(skills_content.render())
            mcp_text = str(mcp_content.render())

            assert "Unable to load" in skills_text
            assert "Unable to load" in mcp_text

    @pytest.mark.asyncio
    async def test_handles_hook_config_load_failure(self):
        """Verify tab handles hook config load failure gracefully."""
        mock_agent = _create_mock_agent()
        app = _TestApp(mock_agent=mock_agent, mock_hook_config=None)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            hooks_content = tab.query_one("#hooks_content", Static)

            content = str(hooks_content.render())
            assert "Unable to load" in content
