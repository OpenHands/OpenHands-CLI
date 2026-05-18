"""UserMessageController - handles sending user input into a conversation."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable

    from openhands_cli.tui.core.conversation_runner import ConversationRunner
    from openhands_cli.tui.core.runner_registry import RunnerRegistry
    from openhands_cli.tui.core.state import ConversationContainer


# Planning mode instructions prepended to user messages when in plan mode.
# These work in tandem with AlwaysConfirm policy — the prompt guides the agent
# toward planning behavior, while AlwaysConfirm provides a hard safety net
# requiring user approval before any action executes.
PLANNING_MODE_INSTRUCTIONS = """
<PLANNING_MODE>
You are currently in PLANNING MODE. This is a read-only mode.

STRICTLY FORBIDDEN actions:
- DO NOT use CmdRunAction (terminal/shell commands)
- DO NOT use FileWriteAction or FileEditAction (file modifications)
- DO NOT use BrowseInteractiveAction
- DO NOT execute, compile, or run any code
- The ONLY file you may create or edit is PLAN.md in the workspace root

Your role in this mode:
1. Ask clarifying questions to understand requirements fully
2. Analyze the existing codebase using read-only tools (file reading, search)
3. Create a structured PLAN.md with:
   - Problem statement and requirements
   - Proposed approach and architecture
   - Step-by-step implementation plan
   - Potential challenges and mitigations
   - Success criteria and testing approach
4. Identify edge cases, dependencies, and constraints
5. Present the plan and ask the user to switch to /code mode when ready

IMPORTANT: Even if the user asks you to "just do it" or "go ahead," stay in
planning mode. They must explicitly use /code to enable execution.
</PLANNING_MODE>

User's request:
"""


class UserMessageController:
    def __init__(
        self,
        *,
        state: ConversationContainer,
        runners: RunnerRegistry,
        run_worker: Callable[..., object],
        headless_mode: bool,
    ) -> None:
        self._state = state
        self._runners = runners
        self._run_worker = run_worker
        self._headless_mode = headless_mode

    async def handle_user_message(self, content: str) -> None:
        """Handle a user-initiated message (starts a new user turn).

        Note: The refinement iteration counter is reset by ConversationManager
        before calling this method. For system-generated refinement messages,
        use handle_refinement_message() instead.

        Args:
            content: The user's message content.
        """
        # Guard: no conversation_id means switching in progress
        if self._state.conversation_id is None:
            return

        runner = self._runners.get_or_create(self._state.conversation_id)

        # Render user message to UI (show original content without instructions)
        runner.visualizer.render_user_message(content)

        # Update conversation title (for history panel)
        self._state.set_conversation_title(content)

        # Apply planning mode instructions if in plan mode
        message_content = self._apply_mode_instructions(content)

        await self._process_message(runner, message_content)

    def _apply_mode_instructions(self, content: str) -> str:
        """Apply mode-specific instructions to the message content.

        In planning mode, prepends instructions that guide the agent to focus
        on understanding requirements and generating a PLAN.md file instead
        of executing code.

        Args:
            content: The original user message content.

        Returns:
            The message content with mode-specific instructions applied.
        """
        if self._state.agent_mode == "plan":
            return f"{PLANNING_MODE_INSTRUCTIONS}{content}"
        return content

    async def handle_refinement_message(self, content: str) -> None:
        """Handle a system-generated refinement message.

        Unlike handle_user_message(), this does NOT reset the refinement
        iteration counter or update the conversation title. This allows
        the iterative refinement loop to track progress correctly.

        Args:
            content: The refinement message content.
        """
        # Guard: no conversation_id means switching in progress
        if self._state.conversation_id is None:
            return

        runner = self._runners.get_or_create(self._state.conversation_id)

        # Render refinement message - preserves the iteration counter
        runner.visualizer.render_refinement_message(content)

        # Note: Don't update conversation title for refinement messages

        # Apply planning mode instructions to refinements too — the agent
        # must stay in planning mode even through system-generated follow-ups.
        message_content = self._apply_mode_instructions(content)

        await self._process_message(runner, message_content)

    async def _process_message(self, runner: ConversationRunner, content: str) -> None:
        """Process a message by queuing or starting a new run.

        Args:
            runner: The conversation runner to use.
            content: The message content to process.
        """

        if runner.is_running:
            await runner.queue_message(content)
            return

        self._run_worker(
            runner.process_message_async(content, self._headless_mode),
            name="process_message",
        )
