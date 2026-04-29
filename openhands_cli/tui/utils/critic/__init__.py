"""Critic utilities used by the CLI."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from openhands_cli.tui.utils.critic.feedback import send_critic_inference_event
    from openhands_cli.tui.utils.critic.refinement import (
        CliIterativeRefinementConfig,
        RefinementDecision,
        build_refinement_message,
        evaluate_iterative_refinement,
        get_high_probability_issues,
    )
    from openhands_cli.tui.utils.critic.visualization import create_critic_collapsible


__all__ = [
    "CliIterativeRefinementConfig",
    "RefinementDecision",
    "build_refinement_message",
    "create_critic_collapsible",
    "evaluate_iterative_refinement",
    "get_high_probability_issues",
    "send_critic_inference_event",
]


def __getattr__(name: str) -> Any:
    if name in {
        "CliIterativeRefinementConfig",
        "RefinementDecision",
        "build_refinement_message",
        "evaluate_iterative_refinement",
        "get_high_probability_issues",
    }:
        module = import_module("openhands_cli.tui.utils.critic.refinement")
        return getattr(module, name)
    if name == "send_critic_inference_event":
        module = import_module("openhands_cli.tui.utils.critic.feedback")
        return getattr(module, name)
    if name == "create_critic_collapsible":
        module = import_module("openhands_cli.tui.utils.critic.visualization")
        return getattr(module, name)
    raise AttributeError(name)
