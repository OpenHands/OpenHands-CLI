"""Tests for ResourcesTab component."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from openhands_cli.tui.content.resources import (
    HookInfo,
    LoadedResourcesInfo,
    SkillInfo,
)
from openhands_cli.tui.modals.settings.components.resources_tab import ResourcesTab


def _create_mock_agent(
    mcp_config: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock Agent with configurable MCP config."""
    mock_agent = MagicMock()
    mock_agent.mcp_config = mcp_config or {"mcpServers": {}}
    return mock_agent


def _create_resources(
    skills: list[SkillInfo] | None = None,
    hooks: list[HookInfo] | None = None,
) -> LoadedResourcesInfo:
    """Create a LoadedResourcesInfo with configurable skills and hooks."""
    return LoadedResourcesInfo(
        skills=skills or [],
        hooks=hooks or [],
        mcps=[],
    )


class _TestApp(App):
    """Small Textual app to mount the tab under test."""

    def __init__(
        self,
        mock_agent: MagicMock | None = None,
        mock_resources: LoadedResourcesInfo | None = None,
    ):
        super().__init__()
        self.mock_agent = mock_agent
        self.mock_resources = mock_resources or LoadedResourcesInfo()

    def compose(self) -> ComposeResult:
        with patch(
            "openhands_cli.tui.modals.settings.components.resources_tab.AgentStore"
        ) as mock_store_class:
            mock_store = MagicMock()
            mock_store.load_from_disk.return_value = self.mock_agent
            mock_store_class.return_value = mock_store

            with patch(
                "openhands_cli.tui.modals.settings.components.resources_tab.collect_loaded_resources"
            ) as mock_collect:
                mock_collect.return_value = self.mock_resources
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
        mock_agent = _create_mock_agent()
        mock_resources = _create_resources(skills=[])
        app = _TestApp(mock_agent=mock_agent, mock_resources=mock_resources)

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
            SkillInfo(name="test_skill", description="A test skill", source="local"),
            SkillInfo(name="another_skill", description="Another skill"),
        ]
        mock_agent = _create_mock_agent()
        mock_resources = _create_resources(skills=skills)
        app = _TestApp(mock_agent=mock_agent, mock_resources=mock_resources)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            skills_content = tab.query_one("#skills_content", Static)

            content = str(skills_content.render())
            assert "test_skill" in content
            assert "another_skill" in content

    @pytest.mark.asyncio
    async def test_hooks_section_shows_no_hooks_when_empty(self):
        """Verify hooks section shows 'No hooks loaded' when empty."""
        mock_agent = _create_mock_agent()
        mock_resources = _create_resources(hooks=[])
        app = _TestApp(mock_agent=mock_agent, mock_resources=mock_resources)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            hooks_content = tab.query_one("#hooks_content", Static)

            content = str(hooks_content.render())
            assert "No hooks loaded" in content

    @pytest.mark.asyncio
    async def test_hooks_section_shows_hooks_when_present(self):
        """Verify hooks section shows hook types and commands when present."""
        hooks = [
            HookInfo(hook_type="pre_tool_use", commands=["cmd1", "cmd2"]),
            HookInfo(hook_type="post_tool_use", commands=["cmd3"]),
        ]
        mock_agent = _create_mock_agent()
        mock_resources = _create_resources(hooks=hooks)
        app = _TestApp(mock_agent=mock_agent, mock_resources=mock_resources)

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
        # When agent is None, skills show "No skills loaded" and MCP shows error
        app = _TestApp(mock_agent=None)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            skills_content = tab.query_one("#skills_content", Static)
            mcp_content = tab.query_one("#mcp_content", Static)

            # Skills should show "No skills loaded" (from empty resources)
            skills_text = str(skills_content.render())
            assert "No skills loaded" in skills_text

            # MCP should show error since agent is None
            mcp_text = str(mcp_content.render())
            assert "Unable to load" in mcp_text

    @pytest.mark.asyncio
    async def test_handles_empty_resources(self):
        """Verify tab handles empty resources gracefully."""
        mock_agent = _create_mock_agent()
        mock_resources = _create_resources()  # Empty resources
        app = _TestApp(mock_agent=mock_agent, mock_resources=mock_resources)

        async with app.run_test():
            tab = app.query_one(ResourcesTab)
            skills_content = tab.query_one("#skills_content", Static)
            hooks_content = tab.query_one("#hooks_content", Static)

            skills_text = str(skills_content.render())
            hooks_text = str(hooks_content.render())

            assert "No skills loaded" in skills_text
            assert "No hooks loaded" in hooks_text
