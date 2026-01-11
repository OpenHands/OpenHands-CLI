"""Tests for ACP resume behavior and race condition prevention.

This module tests the scenario described in issue #268 where:
1. User sends a message while the agent is STILL PROCESSING
2. This creates two parallel event streams writing to overlapping indices
3. Event files get overwritten with different content
4. Eventually causes LLM API errors

The key bug is that when a second prompt() is called while the first is still
running, the code at line 545 overwrites _running_tasks[session_id], allowing
both tasks to run concurrently.

Related to issue #268: ACP resume may create multiple EventLog instances causing
duplicate events.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from acp.schema import TextContentBlock

from openhands.sdk import Message, TextContent
from openhands.sdk.conversation.state import ConversationExecutionStatus
from openhands.sdk.event.llm_convertible.message import MessageEvent
from openhands_cli.acp_impl.agent import OpenHandsACPAgent


@pytest.fixture
def mock_connection():
    """Create a mock ACP connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def acp_agent(mock_connection):
    """Create an OpenHands ACP agent instance."""
    return OpenHandsACPAgent(mock_connection, "always-approve")


class TestACPConcurrentPromptRaceCondition:
    """Test suite for race condition when user sends message while agent processes.

    This reproduces the bug from issue #268 where:
    - 22:25:57 - 22:26:19: Agent processing events 112-119
    - 22:26:22: User sends message - gets index 112 (should be ~120!)
    - 22:26:23: Agent continues at 120-121
    - Two streams now writing to overlapping indices
    """

    @pytest.mark.asyncio
    async def test_concurrent_prompts_create_parallel_tasks(
        self, acp_agent, mock_connection, tmp_path
    ):
        """Test that second prompt while first is running creates parallel tasks.

        This test REPRODUCES the bug described in issue #268.
        The current implementation allows two tasks to run concurrently because
        prompt() overwrites _running_tasks[session_id] without checking if a task
        is already running.
        """
        session_id = str(uuid4())

        # Track concurrent task execution
        concurrent_task_count = []
        tasks_running = []
        first_run_started = asyncio.Event()

        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        mock_conversation.state.execution_status = ConversationExecutionStatus.IDLE

        def mock_send_message(msg):
            pass

        mock_conversation.send_message = mock_send_message

        run_call_count = [0]

        def mock_run():
            run_call_count[0] += 1
            current_run = run_call_count[0]

            # Record how many tasks are currently in _running_tasks
            # and how many are not done
            running_count = sum(
                1 for t in acp_agent._running_tasks.values() if not t.done()
            )
            concurrent_task_count.append(running_count)
            tasks_running.append(f"run_{current_run}_sees_{running_count}_tasks")

            if current_run == 1:
                # First run - signal start and wait
                first_run_started.set()
                # Simulate long-running LLM call
                import time

                time.sleep(0.2)

            mock_conversation.state.execution_status = (
                ConversationExecutionStatus.FINISHED
            )

        mock_conversation.run = mock_run

        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent
            mock_conv.return_value = mock_conversation

            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

        async def first_prompt():
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="First message")],
            )

        async def second_prompt():
            # Wait for first run to start
            await first_run_started.wait()
            # Small delay to ensure first task is registered
            await asyncio.sleep(0.05)
            # Reset status so second prompt can run
            mock_conversation.state.execution_status = ConversationExecutionStatus.IDLE
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="Second message")],
            )

        # Run both prompts concurrently - this should trigger the race condition
        await asyncio.gather(first_prompt(), second_prompt())

        # The bug: both runs should have been called
        assert run_call_count[0] == 2, "Both prompts should have triggered run()"

        # The bug manifests here: the second prompt overwrites _running_tasks
        # so when the second run() checks, it only sees 1 task (itself)
        # But in reality, two tasks were running concurrently
        #
        # If the bug is present: both runs see only 1 task
        # If the bug is fixed: second prompt should wait or be queued

        # This assertion documents the current buggy behavior
        # When the bug is fixed, this test should be updated
        print(f"Tasks running observations: {tasks_running}")
        print(f"Concurrent task counts: {concurrent_task_count}")

        # The bug: _running_tasks only tracks ONE task at a time because
        # the second prompt overwrites the first task's entry
        # So each run() only sees 1 task, but they're actually running in parallel

    @pytest.mark.asyncio
    async def test_concurrent_prompts_cause_duplicate_events(
        self, acp_agent, mock_connection, tmp_path
    ):
        """Test that concurrent prompts can cause duplicate/overlapping events.

        This reproduces the symptom from issue #268 where events get duplicate indices.
        """
        session_id = str(uuid4())

        # Track all events with their "indices" (simulated)
        event_indices = []
        event_index = [0]
        first_run_started = asyncio.Event()

        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        mock_conversation.state.execution_status = ConversationExecutionStatus.IDLE

        def mock_send_message(msg):
            pass

        mock_conversation.send_message = mock_send_message

        callbacks_holder = []

        def mock_run():
            # Simulate writing events with indices
            # In the real bug, both runs would try to write to overlapping indices
            current_index = event_index[0]
            event_index[0] += 1

            event_indices.append(current_index)

            # Create and emit event
            message = Message(
                role="assistant",
                content=[TextContent(text=f"Event at index {current_index}")],
            )
            event = MessageEvent(source="agent", llm_message=message)

            for callback in callbacks_holder:
                callback(event)

            if current_index == 0:
                first_run_started.set()
                # Simulate long processing
                import time

                time.sleep(0.1)

            mock_conversation.state.execution_status = (
                ConversationExecutionStatus.FINISHED
            )

        mock_conversation.run = mock_run

        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent

            def capture_callbacks(*args, **kwargs):
                if "callbacks" in kwargs and kwargs["callbacks"]:
                    callbacks_holder.extend(kwargs["callbacks"])
                return mock_conversation

            mock_conv.side_effect = capture_callbacks

            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

        async def first_prompt():
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="First")],
            )

        async def second_prompt():
            await first_run_started.wait()
            await asyncio.sleep(0.02)
            mock_conversation.state.execution_status = ConversationExecutionStatus.IDLE
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="Second")],
            )

        await asyncio.gather(first_prompt(), second_prompt())

        print(f"Event indices written: {event_indices}")

        # In the buggy scenario, both prompts run concurrently and could
        # write to overlapping indices if they share the same EventLog

    @pytest.mark.asyncio
    async def test_running_task_overwritten_on_concurrent_prompt(
        self, acp_agent, mock_connection, tmp_path
    ):
        """Test that _running_tasks[session_id] gets overwritten on second prompt.

        This directly tests the bug mechanism: line 545 in agent.py does
        `self._running_tasks[session_id] = run_task` without checking if
        a task is already running.
        """
        session_id = str(uuid4())

        first_task_ref = []
        second_task_ref = []
        first_run_started = asyncio.Event()
        task_was_overwritten = [False]

        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        mock_conversation.state.execution_status = ConversationExecutionStatus.IDLE

        def mock_send_message(msg):
            pass

        mock_conversation.send_message = mock_send_message

        run_count = [0]

        def mock_run():
            run_count[0] += 1
            current_run = run_count[0]

            if current_run == 1:
                # Capture the first task reference
                first_task_ref.append(acp_agent._running_tasks.get(session_id))
                first_run_started.set()
                import time

                time.sleep(0.15)
                # Check if our task was overwritten
                current_task = acp_agent._running_tasks.get(session_id)
                if first_task_ref[0] is not current_task:
                    task_was_overwritten[0] = True
            else:
                second_task_ref.append(acp_agent._running_tasks.get(session_id))

            mock_conversation.state.execution_status = (
                ConversationExecutionStatus.FINISHED
            )

        mock_conversation.run = mock_run

        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent
            mock_conv.return_value = mock_conversation

            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

        async def first_prompt():
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="First")],
            )

        async def second_prompt():
            await first_run_started.wait()
            await asyncio.sleep(0.05)
            mock_conversation.state.execution_status = ConversationExecutionStatus.IDLE
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="Second")],
            )

        await asyncio.gather(first_prompt(), second_prompt())

        # This assertion documents the bug: the first task's reference was overwritten
        assert task_was_overwritten[0], (
            "BUG REPRODUCED: _running_tasks[session_id] was overwritten while "
            "first task was still running. This allows concurrent execution."
        )

        # The first and second tasks should be different objects
        assert first_task_ref[0] is not second_task_ref[0], (
            "First and second tasks should be different objects"
        )


class TestACPPauseResumeBehavior:
    """Test suite for pause/resume scenarios (cancel then new prompt)."""

    @pytest.mark.asyncio
    async def test_cancel_waits_for_running_task(self, acp_agent, mock_connection):
        """Test that cancel() waits for the running task to complete."""
        session_id = str(uuid4())

        mock_conversation = MagicMock()
        mock_conversation.state.execution_status = ConversationExecutionStatus.RUNNING

        pause_called = asyncio.Event()

        def mock_pause():
            pause_called.set()
            mock_conversation.state.execution_status = (
                ConversationExecutionStatus.PAUSED
            )

        mock_conversation.pause = mock_pause

        acp_agent._active_sessions[session_id] = mock_conversation

        task_completed = asyncio.Event()

        async def slow_task():
            await pause_called.wait()
            await asyncio.sleep(0.1)
            task_completed.set()

        running_task = asyncio.create_task(slow_task())
        acp_agent._running_tasks[session_id] = running_task

        await acp_agent.cancel(session_id=session_id)

        assert task_completed.is_set(), (
            "cancel() should wait for running task to complete"
        )
        assert running_task.done(), "Running task should be done after cancel()"

    @pytest.mark.asyncio
    async def test_same_conversation_instance_after_pause_resume(
        self, acp_agent, mock_connection, tmp_path
    ):
        """Test that the same conversation instance is used after pause/resume."""
        session_id = str(uuid4())

        conversation_instances = []

        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        mock_conversation.state.execution_status = ConversationExecutionStatus.IDLE

        def mock_pause():
            mock_conversation.state.execution_status = (
                ConversationExecutionStatus.PAUSED
            )

        mock_conversation.pause = mock_pause

        def mock_send_message(msg):
            mock_conversation.state.execution_status = ConversationExecutionStatus.IDLE

        mock_conversation.send_message = mock_send_message

        def mock_run():
            mock_conversation.state.execution_status = (
                ConversationExecutionStatus.FINISHED
            )

        mock_conversation.run = mock_run

        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent
            mock_conv.return_value = mock_conversation

            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

            conversation_instances.append(acp_agent._active_sessions[session_id])

            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="First message")],
            )
            conversation_instances.append(acp_agent._active_sessions[session_id])

            await acp_agent.cancel(session_id=session_id)
            conversation_instances.append(acp_agent._active_sessions[session_id])

            mock_conversation.state.execution_status = ConversationExecutionStatus.IDLE
            await acp_agent.prompt(
                session_id=session_id,
                prompt=[TextContentBlock(type="text", text="Second message")],
            )
            conversation_instances.append(acp_agent._active_sessions[session_id])

        assert all(
            inst is conversation_instances[0] for inst in conversation_instances
        ), "Different conversation instances were used"

        mock_conv.assert_called_once()

    @pytest.mark.asyncio
    async def test_prompt_cleans_up_running_task(
        self, acp_agent, mock_connection, tmp_path
    ):
        """Test that prompt() properly cleans up _running_tasks in its finally block."""
        session_id = str(uuid4())

        mock_conversation = MagicMock()
        mock_conversation.state.events = []
        mock_conversation.state.execution_status = ConversationExecutionStatus.IDLE

        def mock_send_message(msg):
            pass

        mock_conversation.send_message = mock_send_message

        def mock_run():
            mock_conversation.state.execution_status = (
                ConversationExecutionStatus.FINISHED
            )

        mock_conversation.run = mock_run

        with (
            patch("openhands_cli.acp_impl.agent.load_agent_specs") as mock_load,
            patch("openhands_cli.acp_impl.agent.Conversation") as mock_conv,
        ):
            mock_agent = MagicMock()
            mock_agent.llm.model = "test-model"
            mock_load.return_value = mock_agent
            mock_conv.return_value = mock_conversation

            response = await acp_agent.new_session(cwd=str(tmp_path), mcp_servers=[])
            session_id = response.session_id

        await acp_agent.prompt(
            session_id=session_id,
            prompt=[TextContentBlock(type="text", text="Hello")],
        )

        assert session_id not in acp_agent._running_tasks, (
            "_running_tasks should be cleaned up after prompt completes"
        )
