"""Tests for background startup handling in UserMessageController."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from openhands_cli.tui.core.user_message_controller import UserMessageController


if TYPE_CHECKING:
    from openhands_cli.tui.core.runner_registry import RunnerRegistry


class _FakeRunner:
    def __init__(
        self,
        *,
        is_running: bool = False,
        is_warming_up: bool = False,
        is_ready: bool = True,
    ) -> None:
        self.is_running = is_running
        self.is_warming_up = is_warming_up
        self.is_ready = is_ready
        self.visualizer = MagicMock()
        self.queue_message = AsyncMock()
        self.process_message_job = object()
        self.process_pending_job = object()
        self.process_message_async = MagicMock(return_value=self.process_message_job)
        self.process_pending_messages_async = MagicMock(
            return_value=self.process_pending_job
        )


class _FakeRunners:
    def __init__(self, runner: _FakeRunner) -> None:
        self.runner = runner
        self.enqueued: list[tuple[uuid.UUID, str]] = []
        self.started: list[uuid.UUID] = []
        self.pending_messages: dict[uuid.UUID, list[str]] = {}

    def get_or_create(self, conversation_id: uuid.UUID) -> _FakeRunner:
        return self.runner

    def enqueue_pending_message(self, conversation_id: uuid.UUID, content: str) -> None:
        self.enqueued.append((conversation_id, content))

    def start_prewarm(self, conversation_id: uuid.UUID) -> None:
        self.started.append(conversation_id)

    def pop_pending_messages(self, conversation_id: uuid.UUID) -> list[str]:
        return self.pending_messages.pop(conversation_id, [])


@pytest.mark.asyncio
async def test_handle_user_message_queues_until_runner_is_ready() -> None:
    """Early submits should be accepted and queued until warmup finishes."""
    conversation_id = uuid.uuid4()
    state = MagicMock()
    state.conversation_id = conversation_id
    run_worker = MagicMock()
    runner = _FakeRunner(is_ready=False)
    runners = _FakeRunners(runner)
    controller = UserMessageController(
        state=state,
        runners=cast("RunnerRegistry", runners),
        run_worker=run_worker,
        headless_mode=False,
    )

    await controller.handle_user_message("hello")

    runner.visualizer.render_user_message.assert_called_once_with("hello")
    state.set_conversation_title.assert_called_once_with("hello")
    assert runners.enqueued == [(conversation_id, "hello")]
    assert runners.started == [conversation_id]
    run_worker.assert_not_called()


@pytest.mark.asyncio
async def test_handle_user_message_starts_processing_when_runner_is_ready() -> None:
    """Ready runners should process immediately without queueing."""
    conversation_id = uuid.uuid4()
    state = MagicMock()
    state.conversation_id = conversation_id
    run_worker = MagicMock()
    runner = _FakeRunner(is_ready=True)
    runners = _FakeRunners(runner)
    controller = UserMessageController(
        state=state,
        runners=cast("RunnerRegistry", runners),
        run_worker=run_worker,
        headless_mode=False,
    )

    await controller.handle_user_message("hello")

    assert runners.enqueued == []
    assert runners.started == []
    run_worker.assert_called_once_with(
        runner.process_message_job,
        name="process_message",
    )


@pytest.mark.asyncio
async def test_flush_pending_messages_starts_batch_processing() -> None:
    """Queued pre-rendered messages should flush in a single worker job."""
    conversation_id = uuid.uuid4()
    state = MagicMock()
    state.conversation_id = conversation_id
    run_worker = MagicMock()
    runner = _FakeRunner(is_ready=True)
    runners = _FakeRunners(runner)
    runners.pending_messages[conversation_id] = ["one", "two"]
    controller = UserMessageController(
        state=state,
        runners=cast("RunnerRegistry", runners),
        run_worker=run_worker,
        headless_mode=True,
    )

    await controller.flush_pending_messages(conversation_id)

    run_worker.assert_called_once_with(
        runner.process_pending_job,
        name="process_pending_messages",
    )
