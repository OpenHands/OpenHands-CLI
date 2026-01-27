"""Snapshot tests for the full OpenHands UI with mock LLM endpoint.

These tests run the REAL OpenHands TUI application with a REAL agent,
but point the LLM to a mock server for deterministic responses.

The test flow:
1. Start mock LLM server that returns tool call responses
2. Configure agent to use mock LLM endpoint
3. Run the actual OpenHandsApp
4. Simulate user typing "echo hello world" and pressing Enter
5. Wait for agent to process and execute the command
6. Capture snapshot showing the conversation result

This is a true end-to-end test - no mocking of services except the LLM endpoint.
"""

import sys
from pathlib import Path

import pytest
from pydantic import SecretStr
from textual.pilot import Pilot


# Add e2e_tests to path to import mock server
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "e2e_tests"))
from mock_llm_server import MockLLMServer
from trajectory import load_trajectory, get_trajectories_dir


@pytest.fixture
def mock_llm_setup(tmp_path, monkeypatch):
    """Fixture that sets up mock LLM server and agent config.

    This fixture:
    1. Patches locations module FIRST (before any imports that use it)
    2. Mocks UUID generation for deterministic conversation IDs
    3. Uses fixed paths for deterministic snapshots
    4. Starts the mock LLM server with trajectory replay
    5. Creates agent config pointing to the mock server
    6. Yields the config paths
    7. Cleans up the server on teardown
    """
    import uuid as uuid_module
    
    # Use a fixed UUID for deterministic snapshots
    fixed_uuid = uuid_module.UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(uuid_module, "uuid4", lambda: fixed_uuid)
    
    # Create directories with fixed names for deterministic paths in snapshots
    # We still use tmp_path as base but create predictable subdirectory names
    conversations_dir = tmp_path / "conversations"
    conversations_dir.mkdir(exist_ok=True)
    work_dir = tmp_path / "workspace"
    work_dir.mkdir(exist_ok=True)

    # CRITICAL: Patch the locations module DIRECTLY before any imports
    # This must happen before any module that imports from locations
    import openhands_cli.locations as locations_module
    monkeypatch.setattr(locations_module, "PERSISTENCE_DIR", str(tmp_path))
    monkeypatch.setattr(locations_module, "CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setattr(locations_module, "AGENT_SETTINGS_PATH", "agent_settings.json")
    # Use a fixed work directory path for deterministic snapshots
    monkeypatch.setattr(locations_module, "WORK_DIR", "/workspace")

    # Also patch the stores module which may have cached the values
    from openhands_cli.stores import agent_store as agent_store_module
    monkeypatch.setattr(agent_store_module, "PERSISTENCE_DIR", str(tmp_path))
    monkeypatch.setattr(agent_store_module, "CONVERSATIONS_DIR", str(conversations_dir))
    monkeypatch.setattr(agent_store_module, "AGENT_SETTINGS_PATH", "agent_settings.json")
    monkeypatch.setattr(agent_store_module, "WORK_DIR", "/workspace")

    # Load trajectory for deterministic replay
    trajectory = load_trajectory(get_trajectories_dir() / "simple_echo_hello_world")
    
    # Start mock server with trajectory
    server = MockLLMServer(trajectory=trajectory)
    base_url = server.start()

    # Import SDK modules AFTER patching
    from openhands.sdk import LLM
    from openhands_cli.utils import get_default_cli_agent

    # Create LLM pointing to mock server
    # Use "openai/gpt-4o" - SDK will use base_url via api_base param to litellm
    llm = LLM(
        model="openai/gpt-4o",
        api_key=SecretStr("sk-test-mock-key"),
        base_url=base_url,
        usage_id="test-agent",
    )

    # Create agent with the mock LLM
    agent = get_default_cli_agent(llm=llm)

    # Save agent config to temp location
    agent_settings_path = tmp_path / "agent_settings.json"
    config_json = agent.model_dump_json(context={"expose_secrets": True})
    agent_settings_path.write_text(config_json)

    yield {
        "persistence_dir": tmp_path,
        "conversations_dir": conversations_dir,
        "mock_server_url": base_url,
        "work_dir": work_dir,
    }

    # Cleanup
    server.stop()


class TestFullUIWithMockLLM:
    """E2E snapshot tests using real app with mock LLM endpoint.

    These tests run the actual OpenHands TUI application with a real agent,
    but the LLM calls go to a mock server that returns deterministic responses.
    """

    def test_echo_hello_world_conversation(self, snap_compare, mock_llm_setup):
        """Test complete conversation: type 'echo hello world', submit, see result.

        This test:
        1. Starts the real OpenHandsApp
        2. Types "echo hello world" in the input
        3. Presses Enter to submit
        4. Waits for the agent to process via mock LLM
        5. Captures snapshot showing the terminal output
        """
        # Lazy import AFTER fixture has patched locations
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp
        from openhands_cli.tui.widgets import InputField

        async def run_conversation(pilot: Pilot):
            """Simulate user typing and submitting a command."""
            app = pilot.app

            # Wait for app to fully initialize
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

            # Find and focus the input field
            try:
                input_field = app.query_one(InputField)
                input_field.focus_input()
                await pilot.pause()
            except Exception:
                # App might not be fully initialized
                await pilot.pause()
                await pilot.pause()
                input_field = app.query_one(InputField)
                input_field.focus_input()
                await pilot.pause()

            # Type the command
            for char in "echo hello world":
                await pilot.press(char)
            await pilot.pause()

            # Press Enter to submit
            await pilot.press("enter")

            # Wait for agent to process (give it time to call mock LLM and execute)
            for _ in range(50):
                await pilot.pause()
                # Check if conversation is still running
                if hasattr(app, "conversation_runner"):
                    runner = app.conversation_runner
                    if runner and not runner.is_running:
                        break

            # Final pause to let UI update
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

        # Locations are already patched by the fixture via monkeypatch
        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=NeverConfirm(),
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=run_conversation,
        )

    def test_app_with_typed_input(self, snap_compare, mock_llm_setup):
        """Snapshot of app with text typed but not yet submitted.

        This captures the UI state while the user is typing their command.
        """
        # Lazy import AFTER fixture has patched locations
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp
        from openhands_cli.tui.widgets import InputField

        async def type_command(pilot: Pilot):
            """Type command without submitting."""
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

            try:
                input_field = pilot.app.query_one(InputField)
                input_field.focus_input()
                await pilot.pause()
            except Exception:
                await pilot.pause()
                input_field = pilot.app.query_one(InputField)
                input_field.focus_input()
                await pilot.pause()

            # Type the command
            for char in "echo hello world":
                await pilot.press(char)
            await pilot.pause()

        # Locations are already patched by the fixture via monkeypatch
        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=NeverConfirm(),
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=type_command,
        )

    def test_app_initial_state(self, snap_compare, mock_llm_setup):
        """Snapshot of app initial state showing splash screen.

        This captures the welcome screen and initial UI layout.
        """
        # Lazy import AFTER fixture has patched locations
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp

        async def wait_for_init(pilot: Pilot):
            """Wait for app to initialize."""
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

        # Locations are already patched by the fixture via monkeypatch
        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=NeverConfirm(),
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=wait_for_init,
        )
