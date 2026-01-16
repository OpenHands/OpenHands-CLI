"""Snapshot tests for OpenHands CLI Textual application.

These tests use pytest-textual-snapshot to capture and compare SVG screenshots
of the application at various states. This helps detect visual regressions
and provides a way to debug the UI.

To update snapshots when intentional changes are made:
    pytest tests/snapshots/ --snapshot-update

To run these tests:
    pytest tests/snapshots/

For more information:
    https://github.com/Textualize/pytest-textual-snapshot
"""

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from fastmcp.mcp_config import RemoteMCPServer, StdioMCPServer
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Static

from openhands.tools.task_tracker.definition import TaskItem
from openhands_cli.tui.modals.cloud_link_modal import CloudLinkModal
from openhands_cli.tui.modals.exit_modal import ExitConfirmationModal
from openhands_cli.tui.panels.mcp_side_panel import MCPSidePanel
from openhands_cli.tui.panels.plan_side_panel import PlanSidePanel


if TYPE_CHECKING:
    pass


def _create_mock_agent(mcp_config: dict[str, Any] | None = None) -> Any:
    """Create a mock Agent with MCP configuration."""
    mock_agent = MagicMock()
    mock_agent.mcp_config = mcp_config or {"mcpServers": {}}
    return mock_agent


class TestExitModalSnapshots:
    """Snapshot tests for the ExitConfirmationModal."""

    def test_exit_modal_initial_state(self, snap_compare):
        """Snapshot test for exit confirmation modal initial state."""

        class ExitModalTestApp(App):
            CSS = """
            Screen {
                align: center middle;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Background content")
                yield Footer()

            def on_mount(self) -> None:
                self.push_screen(ExitConfirmationModal())

        assert snap_compare(ExitModalTestApp(), terminal_size=(80, 24))


class TestPlanSidePanelSnapshots:
    """Snapshot tests for the PlanSidePanel."""

    def test_plan_panel_empty_state(self, snap_compare):
        """Snapshot test for plan panel with no tasks."""

        class PlanPanelTestApp(App):
            CSS = """
            Screen {
                layout: horizontal;
            }
            #main_content {
                width: 2fr;
            }
            """

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.conversation_dir = ""
                self.plan_panel: PlanSidePanel | None = None

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content area", id="main_content")
                yield Footer()

            def on_mount(self) -> None:
                self.plan_panel = PlanSidePanel(self)  # type: ignore[arg-type]
                # Toggle to show the panel
                self.plan_panel.toggle()

        assert snap_compare(PlanPanelTestApp(), terminal_size=(100, 30))

    def test_plan_panel_with_tasks(self, snap_compare):
        """Snapshot test for plan panel with various task states."""
        task_list = [
            TaskItem(title="Analyze codebase structure", notes="", status="done"),
            TaskItem(title="Implement feature X", notes="", status="in_progress"),
            TaskItem(
                title="Write unit tests",
                notes="Focus on edge cases",
                status="todo",
            ),
            TaskItem(title="Update documentation", notes="", status="todo"),
        ]

        class PlanPanelWithTasksApp(App):
            CSS = """
            Screen {
                layout: horizontal;
            }
            #main_content {
                width: 2fr;
            }
            """

            def __init__(self, tasks: list[TaskItem], **kwargs):
                super().__init__(**kwargs)
                self.conversation_dir = ""
                self.plan_panel: PlanSidePanel | None = None
                self._tasks = tasks

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content area", id="main_content")
                yield Footer()

            def on_mount(self) -> None:
                self.plan_panel = PlanSidePanel(self)  # type: ignore[arg-type]
                self.plan_panel._task_list = self._tasks
                # Toggle to show the panel
                self.plan_panel.toggle()

        assert snap_compare(
            PlanPanelWithTasksApp(tasks=task_list), terminal_size=(100, 30)
        )

    def test_plan_panel_all_done(self, snap_compare):
        """Snapshot test for plan panel with all tasks completed."""
        task_list = [
            TaskItem(title="Task 1", notes="", status="done"),
            TaskItem(title="Task 2", notes="", status="done"),
            TaskItem(title="Task 3", notes="", status="done"),
        ]

        class PlanPanelAllDoneApp(App):
            CSS = """
            Screen {
                layout: horizontal;
            }
            #main_content {
                width: 2fr;
            }
            """

            def __init__(self, tasks: list[TaskItem], **kwargs):
                super().__init__(**kwargs)
                self.conversation_dir = ""
                self.plan_panel: PlanSidePanel | None = None
                self._tasks = tasks

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content area", id="main_content")
                yield Footer()

            def on_mount(self) -> None:
                self.plan_panel = PlanSidePanel(self)  # type: ignore[arg-type]
                self.plan_panel._task_list = self._tasks
                # Toggle to show the panel
                self.plan_panel.toggle()

        assert snap_compare(
            PlanPanelAllDoneApp(tasks=task_list), terminal_size=(100, 30)
        )


class TestMCPSidePanelSnapshots:
    """Snapshot tests for the MCPSidePanel."""

    def test_mcp_panel_empty_state(self, snap_compare):
        """Snapshot test for MCP panel with no servers configured."""
        mock_agent = _create_mock_agent({"mcpServers": {}})

        class MCPPanelEmptyApp(App):
            CSS = """
            Screen {
                layout: horizontal;
            }
            #main_content {
                width: 2fr;
            }
            """

            def __init__(self, agent, **kwargs):
                super().__init__(**kwargs)
                self._agent = agent

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content area", id="main_content")
                yield Footer()

            def on_mount(self) -> None:
                panel = MCPSidePanel(agent=self._agent)
                content_area = self.query_one("#content_area", Horizontal)
                content_area.mount(panel)

        assert snap_compare(MCPPanelEmptyApp(agent=mock_agent), terminal_size=(100, 30))

    def test_mcp_panel_with_remote_servers(self, snap_compare):
        """Snapshot test for MCP panel with RemoteMCPServer objects.

        This test verifies the fix for issue #362 where RemoteMCPServer
        objects caused a crash when opening the MCP menu.
        """
        mcp_config = {
            "mcpServers": {
                "notion": RemoteMCPServer(
                    url="https://mcp.notion.com/mcp",
                    transport="http",
                    auth="oauth",
                ),
                "api_server": RemoteMCPServer(
                    url="https://api.example.com/mcp",
                    transport="http",
                    headers={"Authorization": "Bearer token"},
                ),
            }
        }
        mock_agent = _create_mock_agent(mcp_config)

        class MCPPanelWithRemoteServersApp(App):
            CSS = """
            Screen {
                layout: horizontal;
            }
            #main_content {
                width: 2fr;
            }
            """

            def __init__(self, agent, **kwargs):
                super().__init__(**kwargs)
                self._agent = agent

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content area", id="main_content")
                yield Footer()

            def on_mount(self) -> None:
                panel = MCPSidePanel(agent=self._agent)
                content_area = self.query_one("#content_area", Horizontal)
                content_area.mount(panel)

        assert snap_compare(
            MCPPanelWithRemoteServersApp(agent=mock_agent), terminal_size=(100, 30)
        )

    def test_mcp_panel_with_stdio_servers(self, snap_compare):
        """Snapshot test for MCP panel with StdioMCPServer objects."""
        mcp_config = {
            "mcpServers": {
                "local_server": StdioMCPServer(
                    command="python",
                    args=["-m", "mcp_server"],
                    transport="stdio",
                    env={"API_KEY": "secret"},
                ),
            }
        }
        mock_agent = _create_mock_agent(mcp_config)

        class MCPPanelWithStdioServersApp(App):
            CSS = """
            Screen {
                layout: horizontal;
            }
            #main_content {
                width: 2fr;
            }
            """

            def __init__(self, agent, **kwargs):
                super().__init__(**kwargs)
                self._agent = agent

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content area", id="main_content")
                yield Footer()

            def on_mount(self) -> None:
                panel = MCPSidePanel(agent=self._agent)
                content_area = self.query_one("#content_area", Horizontal)
                content_area.mount(panel)

        assert snap_compare(
            MCPPanelWithStdioServersApp(agent=mock_agent), terminal_size=(100, 30)
        )

    def test_mcp_panel_with_mixed_servers(self, snap_compare):
        """Snapshot test for MCP panel with both remote and stdio servers."""
        mcp_config = {
            "mcpServers": {
                "notion": RemoteMCPServer(
                    url="https://mcp.notion.com/mcp",
                    transport="http",
                    auth="oauth",
                ),
                "local_tool": StdioMCPServer(
                    command="npx",
                    args=["@modelcontextprotocol/server-filesystem"],
                    transport="stdio",
                ),
            }
        }
        mock_agent = _create_mock_agent(mcp_config)

        class MCPPanelMixedServersApp(App):
            CSS = """
            Screen {
                layout: horizontal;
            }
            #main_content {
                width: 2fr;
            }
            """

            def __init__(self, agent, **kwargs):
                super().__init__(**kwargs)
                self._agent = agent

            def compose(self) -> ComposeResult:
                with Horizontal(id="content_area"):
                    yield Static("Main content area", id="main_content")
                yield Footer()

            def on_mount(self) -> None:
                panel = MCPSidePanel(agent=self._agent)
                content_area = self.query_one("#content_area", Horizontal)
                content_area.mount(panel)

        assert snap_compare(
            MCPPanelMixedServersApp(agent=mock_agent), terminal_size=(100, 30)
        )


class TestCloudLinkModalSnapshots:
    """Snapshot tests for the CloudLinkModal."""

    def test_cloud_link_modal_disconnected_state(self, snap_compare):
        """Snapshot test for cloud link modal when not connected."""

        class CloudLinkModalDisconnectedApp(App):
            CSS = """
            Screen {
                align: center middle;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Background content")
                yield Footer()

            def on_mount(self) -> None:
                self.push_screen(
                    CloudLinkModal(
                        is_connected=False,
                        cloud_url="https://app.all-hands.dev",
                    )
                )

        assert snap_compare(CloudLinkModalDisconnectedApp(), terminal_size=(80, 24))

    def test_cloud_link_modal_connected_state(self, snap_compare):
        """Snapshot test for cloud link modal when connected."""

        class CloudLinkModalConnectedApp(App):
            CSS = """
            Screen {
                align: center middle;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Background content")
                yield Footer()

            def on_mount(self) -> None:
                self.push_screen(
                    CloudLinkModal(
                        is_connected=True,
                        cloud_url="https://app.all-hands.dev",
                    )
                )

        assert snap_compare(CloudLinkModalConnectedApp(), terminal_size=(80, 24))
