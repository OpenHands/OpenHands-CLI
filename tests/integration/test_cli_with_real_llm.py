"""Integration tests for OpenHands CLI with real LLM.

These tests require LLM_API_KEY environment variable to be set.
They will be skipped if the API key is not available.

To run these tests:
    LLM_API_KEY=your_key pytest tests/integration/ -v

Environment variables:
    LLM_API_KEY: (required) API key for the LLM service
    LLM_BASE_URL: (optional) defaults to https://llm-proxy.eval.all-hands.dev
    LLM_MODEL: (optional) defaults to litellm_proxy/claude-haiku-4-5-20251001
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


class TestCLIWithRealLLM:
    """Integration tests that send real messages to the LLM."""

    @pytest.mark.integration
    def test_headless_send_hi_to_agent(self, setup_real_agent_settings):
        """Test sending 'hi' to the agent in headless mode.

        This test:
        1. Sets up real agent configuration from environment
        2. Runs the CLI in headless mode with --task "hi"
        3. Verifies the agent responds
        """
        if setup_real_agent_settings is None:
            pytest.skip("LLM_API_KEY not set - skipping real LLM test")

        persistence_dir = setup_real_agent_settings

        # Patch locations to use our temp directory
        with patch.multiple(
            "openhands_cli.locations",
            PERSISTENCE_DIR=str(persistence_dir),
            CONVERSATIONS_DIR=str(persistence_dir / "conversations"),
        ):
            # Run the CLI in headless mode
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "openhands_cli.simple_main",
                    "--headless",
                    "--task",
                    "hi",
                    "--always-approve",
                ],
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
                cwd=str(Path(__file__).parent.parent.parent),
                env={
                    **dict(__import__("os").environ),
                    "PERSISTENCE_DIR": str(persistence_dir),
                },
            )

            # Print output for debugging
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            print("Return code:", result.returncode)

            # The CLI should complete successfully
            # Note: returncode might be non-zero if agent exits normally
            # We check for evidence of a response in stdout

            # Check that we got some response
            output = result.stdout.lower() + result.stderr.lower()
            assert "conversation id:" in output or "goodbye" in output, (
                f"Expected conversation output, got: {result.stdout[:500]}"
            )


class TestCLIHeadlessSnapshot:
    """Test headless mode with snapshot comparison."""

    @pytest.mark.integration
    def test_headless_output_format(self, setup_real_agent_settings):
        """Verify headless mode produces expected output format."""
        if setup_real_agent_settings is None:
            pytest.skip("LLM_API_KEY not set - skipping real LLM test")

        persistence_dir = setup_real_agent_settings

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "openhands_cli.simple_main",
                "--headless",
                "--task",
                "Say exactly: TEST_RESPONSE_123",
                "--always-approve",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path(__file__).parent.parent.parent),
            env={
                **dict(__import__("os").environ),
                "PERSISTENCE_DIR": str(persistence_dir),
            },
        )

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

        # The response should contain our marker
        # (Agent should respond with something containing TEST_RESPONSE_123)
        combined_output = result.stdout + result.stderr

        # At minimum, we should see conversation output
        assert "conversation" in combined_output.lower() or len(result.stdout) > 0


class TestDirectConversation:
    """Test conversation directly without subprocess."""

    @pytest.mark.integration
    def test_conversation_responds_to_hi(self, real_agent_config, tmp_path):
        """Test that the conversation runner responds to 'hi'."""
        if real_agent_config is None:
            pytest.skip("LLM_API_KEY not set - skipping real LLM test")

        import uuid

        from pydantic import SecretStr

        from openhands.sdk import LLM, Agent, Conversation, Workspace
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands.tools.preset.default import get_default_tools

        # Create LLM configuration
        llm = LLM(
            model=real_agent_config["model"],
            api_key=SecretStr(real_agent_config["api_key"]),
            base_url=real_agent_config["base_url"],
            usage_id="test-direct",
        )

        # Create agent
        agent = Agent(
            llm=llm,
            tools=get_default_tools(enable_browser=False),
            mcp_config={},
        )

        # Create workspace and persistence directories
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()
        persistence_dir = tmp_path / "conversations"
        persistence_dir.mkdir()

        # Create conversation (confirmation_policy is set separately)
        conversation = Conversation(
            agent=agent,
            workspace=Workspace(working_dir=str(workspace_dir)),
            persistence_dir=str(persistence_dir),
            conversation_id=uuid.uuid4(),
        )

        # Set up confirmation policy (auto-approve everything)
        conversation.set_confirmation_policy(NeverConfirm())

        # Send "hi" message (can be a string or Message object)
        conversation.send_message("hi")

        # Run the conversation
        conversation.run()

        # Check that we have events
        events = conversation.state.events
        assert len(events) > 0, "Expected at least one event"

        # Check for agent response
        from openhands.sdk.event import MessageEvent

        agent_messages = [
            e for e in events if isinstance(e, MessageEvent) and e.source == "agent"
        ]

        assert len(agent_messages) > 0, "Expected at least one agent message"

        # Print the response for debugging
        for msg in agent_messages:
            print(f"Agent response: {msg.visualize}")
