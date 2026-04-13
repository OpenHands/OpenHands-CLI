"""Tests for setup module — builtin agent registration."""

from collections.abc import Iterator

import pytest

from openhands.sdk.subagent.registry import (
    _agent_factories,
    _reset_registry_for_tests,
    get_agent_factory,
)
from openhands_cli.setup import ensure_builtin_agents_registered


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    """Reset the global agent registry before and after every test."""
    _reset_registry_for_tests()
    yield
    _reset_registry_for_tests()


@pytest.fixture(autouse=True)
def _reset_registration_flag() -> None:
    """Reset the module-level guard so each test starts fresh."""
    import openhands_cli.setup as _mod

    _mod._builtin_agents_registered = False


def test_ensure_builtin_agents_registered_populates_registry() -> None:
    """Calling ensure_builtin_agents_registered should populate the registry."""
    assert len(_agent_factories) == 0
    ensure_builtin_agents_registered()
    assert len(_agent_factories) > 0


def test_default_agent_is_registered() -> None:
    """The 'default' agent type must be resolvable after registration."""
    ensure_builtin_agents_registered()
    factory = get_agent_factory("default")
    assert factory is not None


def test_builtin_agent_names() -> None:
    """Expected built-in agent names should all be present."""
    ensure_builtin_agents_registered()
    names = set(_agent_factories.keys())
    assert "default" in names
    assert "bash" in names or "bash-runner" in names
    assert "explore" in names or "code-explorer" in names


def test_idempotent() -> None:
    """Calling ensure_builtin_agents_registered twice should not raise."""
    ensure_builtin_agents_registered()
    count_after_first = len(_agent_factories)
    ensure_builtin_agents_registered()
    assert len(_agent_factories) == count_after_first


def test_default_agent_has_browser_tools() -> None:
    """The default sub-agent should include browser_tool_set."""
    from pydantic import SecretStr

    from openhands.sdk import LLM

    ensure_builtin_agents_registered()
    factory = get_agent_factory("default")
    llm = LLM(model="gpt-4o", api_key=SecretStr("test-key"), usage_id="test")
    agent = factory.factory_func(llm)
    tool_names = {t.name for t in agent.tools}
    assert tool_names == {
        "terminal",
        "file_editor",
        "task_tracker",
        "browser_tool_set",
    }
