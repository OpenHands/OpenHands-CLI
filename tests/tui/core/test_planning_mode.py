"""Tests for Planning Mode functionality."""

from unittest.mock import MagicMock

from openhands.sdk.event import ActionEvent
from openhands.sdk.llm import MessageToolCall
from openhands.sdk.security.confirmation_policy import ConfirmationPolicyBase
from openhands.sdk.tool import Action
from openhands.sdk.tool.builtins.finish import FinishAction
from openhands.sdk.tool.builtins.think import ThinkAction
from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.task_tracker.definition import TaskTrackerAction
from openhands.tools.terminal.definition import TerminalAction
from openhands_cli.tui.core.conversation_runner import ConversationRunner
from openhands_cli.tui.core.state import AgentMode, ConversationContainer
from openhands_cli.tui.core.user_message_controller import (
    CODE_MODE_INSTRUCTIONS,
    PLANNING_MODE_INSTRUCTIONS,
    UserMessageController,
)


def _create_action_event(action: Action, tool_name: str = "tool") -> ActionEvent:
    """Create an ActionEvent with the SDK fields needed by the runner helpers."""
    tool_call = MessageToolCall(
        id="call_1",
        name=tool_name,
        arguments="{}",
        origin="completion",
    )
    return ActionEvent(
        thought=[],
        action=action,
        tool_name=tool_name,
        tool_call_id="call_1",
        tool_call=tool_call,
        llm_response_id="response_1",
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

    def test_reset_restores_pre_plan_policy(self):
        """Test that reset restores policy saved before plan mode."""
        container = ConversationContainer()
        plan_policy = MagicMock(spec=ConfirmationPolicyBase)
        code_policy = MagicMock(spec=ConfirmationPolicyBase)
        container.confirmation_policy = plan_policy
        container.save_pre_plan_policy(code_policy)

        container.reset_conversation_state()

        assert container.agent_mode == "code"
        assert container.confirmation_policy is code_policy
        assert not container.has_pre_plan_policy

    def test_reset_clears_code_mode_notice(self):
        """Test that reset clears pending code-mode transition notices."""
        container = ConversationContainer()
        container.mark_code_mode_notice_pending()

        container.reset_conversation_state()

        assert not container.consume_code_mode_transition_notice()


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

    def test_save_overwrites_existing_saved_policy(self):
        """Test that save replaces the stored policy."""
        container = ConversationContainer()
        first_policy = MagicMock(spec=ConfirmationPolicyBase)
        second_policy = MagicMock(spec=ConfirmationPolicyBase)

        container.save_pre_plan_policy(first_policy)
        container.save_pre_plan_policy(second_policy)

        restored = container.restore_pre_plan_policy()
        assert restored is second_policy


class TestCodeModeTransitionNotice:
    """Tests for notifying the agent when plan mode ends."""

    def test_code_mode_notice_is_consumed_once(self):
        """Test that the code mode notice is a one-shot flag."""
        container = ConversationContainer()

        assert not container.consume_code_mode_transition_notice()

        container.mark_code_mode_notice_pending()

        assert container.consume_code_mode_transition_notice()
        assert not container.consume_code_mode_transition_notice()

    def test_code_mode_notice_can_be_cleared_without_consuming(self):
        """Test that clearing drops a pending code mode notice."""
        container = ConversationContainer()

        container.mark_code_mode_notice_pending()
        container.clear_code_mode_transition_notice()

        assert not container.consume_code_mode_transition_notice()


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

        # Should mention the task tracker based Agent Plan
        assert "task_tracker" in PLANNING_MODE_INSTRUCTIONS
        assert "Agent Plan" in PLANNING_MODE_INSTRUCTIONS
        assert "PLAN.md" not in PLANNING_MODE_INSTRUCTIONS

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

    def test_apply_mode_instructions_code_mode_transition_notice(self):
        """Test that code mode gets a one-shot transition notice after /code."""
        state = ConversationContainer()
        state.mark_code_mode_notice_pending()

        controller = UserMessageController(
            state=state,
            runners=MagicMock(),
            run_worker=MagicMock(),
            headless_mode=False,
        )

        original_content = "Start implementing the plan"
        result = controller._apply_mode_instructions(original_content)
        next_result = controller._apply_mode_instructions(original_content)

        assert CODE_MODE_INSTRUCTIONS in result
        assert original_content in result
        assert result.index(CODE_MODE_INSTRUCTIONS) < result.index(original_content)
        assert next_result == original_content

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
        assert result.index(PLANNING_MODE_INSTRUCTIONS) < result.index(original_content)


class TestConversationRunnerPlanModeActions:
    """Tests for read-only action enforcement in plan mode."""

    def test_plan_mode_allows_think_and_finish_actions(self):
        """Test that non-mutating built-in actions remain allowed."""
        think_event = _create_action_event(
            ThinkAction(thought="Need a plan"),
            tool_name="think",
        )
        finish_event = _create_action_event(
            FinishAction(message="Plan ready"),
            tool_name="finish",
        )

        assert ConversationRunner._is_action_allowed_in_plan_mode(think_event)
        assert ConversationRunner._is_action_allowed_in_plan_mode(finish_event)

    def test_plan_mode_allows_task_tracker_updates(self):
        """Test that the Agent Plan task tracker can be updated in plan mode."""
        plan_event = _create_action_event(
            TaskTrackerAction(command="plan", task_list=[]),
            tool_name="task_tracker",
        )
        view_event = _create_action_event(
            TaskTrackerAction(command="view"),
            tool_name="task_tracker",
        )

        assert ConversationRunner._is_action_allowed_in_plan_mode(plan_event)
        assert ConversationRunner._is_action_allowed_in_plan_mode(view_event)

    def test_plan_mode_allows_read_only_file_view(self):
        """Test that repository reads are allowed in plan mode."""
        view_event = _create_action_event(
            FileEditorAction(command="view", path="README.md"),
            tool_name="file_editor",
        )

        assert ConversationRunner._is_action_allowed_in_plan_mode(view_event)

    def test_plan_mode_blocks_file_modifications(self):
        """Test that repository writes are blocked in plan mode."""
        create_event = _create_action_event(
            FileEditorAction(
                command="create",
                path="PLAN.md",
                file_text="implementation plan",
            ),
            tool_name="file_editor",
        )
        edit_event = _create_action_event(
            FileEditorAction(
                command="str_replace",
                path="openhands_cli/example.py",
                old_str="old",
                new_str="new",
            ),
            tool_name="file_editor",
        )

        assert not ConversationRunner._is_action_allowed_in_plan_mode(create_event)
        assert not ConversationRunner._is_action_allowed_in_plan_mode(edit_event)

    def test_plan_mode_blocks_terminal_actions(self):
        """Test that terminal commands are blocked in plan mode."""
        terminal_event = _create_action_event(
            TerminalAction(command="pytest"),
            tool_name="terminal",
        )

        assert not ConversationRunner._is_action_allowed_in_plan_mode(terminal_event)

    def test_plan_mode_block_reason_names_actions(self):
        """Test the rejection reason explains the blocked action types."""
        terminal_event = _create_action_event(
            TerminalAction(command="pytest"),
            tool_name="terminal",
        )
        edit_event = _create_action_event(
            FileEditorAction(
                command="str_replace",
                path="openhands_cli/example.py",
                old_str="old",
                new_str="new",
            ),
            tool_name="file_editor",
        )

        reason = ConversationRunner._format_plan_mode_block_reason(
            [terminal_event, edit_event]
        )

        assert "Planning Mode blocks non-read-only actions" in reason
        assert "TerminalAction" in reason
        assert "FileEditorAction" in reason
        assert "/code" in reason
