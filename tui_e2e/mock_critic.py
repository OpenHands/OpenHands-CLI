"""Mock Critic for E2E Testing with Trajectory Replay.

This module provides a mock critic that replays predetermined critic results
from trajectory files. It allows e2e tests to deterministically test
iterative refinement flows without making actual critic API calls.

Usage:
    from tui_e2e.mock_critic import MockCritic
    from tui_e2e.trajectory import load_trajectory

    trajectory = load_trajectory("tests/trajectories/cli447_hi_followup_iterative_case_a")
    mock_critic = MockCritic(trajectory.get_critic_results())

    # The mock critic will return results in order
    result = mock_critic.evaluate(events)  # Returns first critic result
    result = mock_critic.evaluate(events)  # Returns second critic result
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, PrivateAttr

from openhands.sdk.critic import CriticBase
from openhands.sdk.critic.result import CriticResult


if TYPE_CHECKING:
    from openhands.sdk.event.base import LLMConvertibleEvent


class MockCritic(CriticBase):
    """Mock critic that replays predetermined results from a trajectory.

    This critic returns results in the order they appear in the trajectory,
    enabling deterministic testing of iterative refinement flows.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Private attributes for mutable state
    _critic_results: list[dict[str, Any]] = PrivateAttr(default_factory=list)
    _current_index: int = PrivateAttr(default=0)
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def __init__(self, critic_results: list[dict[str, Any]] | None = None, **kwargs):
        """Initialize the mock critic.

        Args:
            critic_results: List of critic result dictionaries to replay.
                Each dict should have 'score', 'message', and optionally 'metadata'.
                If None, returns a default high score (task complete).
        """
        super().__init__(**kwargs)
        self._critic_results = critic_results or []
        self._current_index = 0
        self._lock = threading.Lock()

    def evaluate(
        self,
        events: Sequence["LLMConvertibleEvent"],
        git_patch: str | None = None,
    ) -> CriticResult:
        """Return the next critic result from the trajectory.

        Args:
            events: The conversation events (ignored - we replay from trajectory)
            git_patch: Git patch for code changes (ignored)

        Returns:
            The next CriticResult from the trajectory, or a default high score
            if no more results are available.
        """
        with self._lock:
            if self._current_index >= len(self._critic_results):
                # Return default high score when we run out of results
                return CriticResult(
                    score=0.95,
                    message="Task completed successfully (mock default).",
                    metadata=None,
                )

            result_data = self._critic_results[self._current_index]
            self._current_index += 1

            return CriticResult(
                score=result_data.get("score", 0.5),
                message=result_data.get("message"),
                metadata=result_data.get("metadata"),
            )

    def reset(self) -> None:
        """Reset the replay index to the beginning."""
        with self._lock:
            self._current_index = 0

    @property
    def remaining_results(self) -> int:
        """Get the number of remaining results to replay."""
        with self._lock:
            return len(self._critic_results) - self._current_index


def create_mock_critic_from_trajectory(trajectory: Any) -> MockCritic:
    """Create a mock critic from a trajectory.

    Args:
        trajectory: A Trajectory object with critic results.

    Returns:
        A MockCritic configured to replay the trajectory's critic results.
    """
    return MockCritic(critic_results=trajectory.get_critic_results())
