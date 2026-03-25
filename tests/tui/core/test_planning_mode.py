"""Tests for Planning Mode functionality."""

from openhands_cli.tui.core.state import AgentMode, ConversationContainer
from openhands_cli.tui.core.user_message_controller import (
    PLANNING_MODE_INSTRUCTIONS,
    UserMessageController,
)


class TestAgentMode:
    """Tests for AgentMode type and ConversationContainer.agent_mode."""

    def test_agent_mode_default_is_code(self):
        """Test that the default agent mode is 'code'."""
        container = ConversationContainer()
        assert container.agent_mode == "code"

    def test_agent_mode_can_be_set_to_plan(self):
        """Test that agent mode can be set to 'plan'."""
        container = ConversationContainer()
        container.set_agent_mode("plan")
        assert container.agent_mode == "plan"

    def test_agent_mode_can_be_set_back_to_code(self):
        """Test that agent mode can be switched back to 'code'."""
        container = ConversationContainer()
        container.set_agent_mode("plan")
        container.set_agent_mode("code")
        assert container.agent_mode == "code"

    def test_agent_mode_type_literal_values(self):
        """Test that AgentMode is a Literal type with 'plan' and 'code' values."""
        # These should be valid AgentMode values
        plan_mode: AgentMode = "plan"
        code_mode: AgentMode = "code"
        assert plan_mode == "plan"
        assert code_mode == "code"


class TestPlanningModeInstructions:
    """Tests for PLANNING_MODE_INSTRUCTIONS constant."""

    def test_planning_mode_instructions_exist(self):
        """Test that PLANNING_MODE_INSTRUCTIONS constant exists and is not empty."""
        assert PLANNING_MODE_INSTRUCTIONS
        assert len(PLANNING_MODE_INSTRUCTIONS) > 0

    def test_planning_mode_instructions_contain_key_phrases(self):
        """Test that instructions contain key planning-related phrases."""
        # Should mention not executing code
        assert "DO NOT execute" in PLANNING_MODE_INSTRUCTIONS

        # Should mention PLAN.md
        assert "PLAN.md" in PLANNING_MODE_INSTRUCTIONS

        # Should mention understanding/questions
        assert "understanding" in PLANNING_MODE_INSTRUCTIONS.lower()

        # Should mention confirmation
        assert "confirm" in PLANNING_MODE_INSTRUCTIONS.lower()


class TestUserMessageControllerPlanningMode:
    """Tests for UserMessageController planning mode behavior."""

    def test_apply_mode_instructions_code_mode_returns_original(self):
        """Test that code mode returns the original content unchanged."""
        # Create a minimal mock state
        from unittest.mock import MagicMock

        mock_state = MagicMock()
        mock_state.agent_mode = "code"
        mock_state.conversation_id = None  # Not used in _apply_mode_instructions

        controller = UserMessageController(
            state=mock_state,
            runners=MagicMock(),
            run_worker=MagicMock(),
            headless_mode=False,
        )

        original_content = "Hello, please help me with something"
        result = controller._apply_mode_instructions(original_content)

        assert result == original_content

    def test_apply_mode_instructions_plan_mode_prepends_instructions(self):
        """Test that plan mode prepends instructions to the content."""
        from unittest.mock import MagicMock

        mock_state = MagicMock()
        mock_state.agent_mode = "plan"

        controller = UserMessageController(
            state=mock_state,
            runners=MagicMock(),
            run_worker=MagicMock(),
            headless_mode=False,
        )

        original_content = "Hello, please help me with something"
        result = controller._apply_mode_instructions(original_content)

        # Result should contain the planning instructions
        assert PLANNING_MODE_INSTRUCTIONS in result

        # Result should also contain the original content
        assert original_content in result

        # Instructions should come before the content
        assert result.index(PLANNING_MODE_INSTRUCTIONS) < result.index(original_content)
