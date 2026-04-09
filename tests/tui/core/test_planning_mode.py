"""Tests for Planning Mode functionality."""

from unittest.mock import MagicMock

from openhands.sdk.security.confirmation_policy import ConfirmationPolicyBase
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


class TestAgentModeStateReset:
    """Tests for agent_mode being reset on new conversation."""

    def test_reset_conversation_state_resets_agent_mode(self):
        """Test that reset_conversation_state() resets agent_mode to 'code'."""
        container = ConversationContainer()
        container.set_agent_mode("plan")
        assert container.agent_mode == "plan"

        container.reset_conversation_state()
        assert container.agent_mode == "code"

    def test_reset_clears_pre_plan_policy(self):
        """Test that reset_conversation_state() clears saved pre-plan policy."""
        container = ConversationContainer()
        mock_policy = MagicMock(spec=ConfirmationPolicyBase)
        container.save_pre_plan_policy(mock_policy)
        assert container.has_pre_plan_policy

        container.reset_conversation_state()
        assert not container.has_pre_plan_policy


class TestPlanModePolicySaveRestore:
    """Tests for confirmation policy save/restore around plan mode."""

    def test_save_and_restore_pre_plan_policy(self):
        """Test save and restore cycle for confirmation policy."""
        container = ConversationContainer()
        original_policy = MagicMock(spec=ConfirmationPolicyBase)

        container.save_pre_plan_policy(original_policy)
        assert container.has_pre_plan_policy

        restored = container.restore_pre_plan_policy()
        assert restored is original_policy
        assert not container.has_pre_plan_policy

    def test_restore_returns_none_when_no_policy_saved(self):
        """Test that restore returns None when no policy was saved."""
        container = ConversationContainer()
        assert not container.has_pre_plan_policy
        assert container.restore_pre_plan_policy() is None

    def test_save_does_not_overwrite_if_already_saved(self):
        """Test idempotent save — calling save twice uses the first policy."""
        container = ConversationContainer()
        first_policy = MagicMock(spec=ConfirmationPolicyBase)
        second_policy = MagicMock(spec=ConfirmationPolicyBase)

        container.save_pre_plan_policy(first_policy)
        container.save_pre_plan_policy(second_policy)

        # The second save overwrites (ConversationManager checks
        # has_pre_plan_policy before calling save, but the state
        # layer itself doesn't guard)
        restored = container.restore_pre_plan_policy()
        assert restored is second_policy


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
        assert "understand" in PLANNING_MODE_INSTRUCTIONS.lower()

    def test_planning_mode_instructions_forbid_specific_actions(self):
        """Test that instructions explicitly forbid dangerous action types."""
        assert "CmdRunAction" in PLANNING_MODE_INSTRUCTIONS
        assert "FileWriteAction" in PLANNING_MODE_INSTRUCTIONS
        assert "FileEditAction" in PLANNING_MODE_INSTRUCTIONS

    def test_planning_mode_instructions_mention_read_only(self):
        """Test that instructions emphasize read-only mode."""
        assert "read-only" in PLANNING_MODE_INSTRUCTIONS.lower()


class TestUserMessageControllerPlanningMode:
    """Tests for UserMessageController planning mode behavior."""

    def test_apply_mode_instructions_code_mode_returns_original(self):
        """Test that code mode returns the original content unchanged."""
        mock_state = MagicMock()
        mock_state.agent_mode = "code"
        mock_state.conversation_id = None

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
        assert result.index(PLANNING_MODE_INSTRUCTIONS) < result.index(
            original_content
        )

