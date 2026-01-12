"""Tests for delegate_formatter.py - centralized delegate title formatting."""

import pytest

from openhands_cli.shared.delegate_formatter import format_delegate_title


class TestFormatDelegateTitle:
    """Tests for the main format_delegate_title function."""

    @pytest.mark.parametrize(
        "command,ids,tasks,expected",
        [
            ("spawn", ["agent1"], None, "Spawning 1 sub-agent(s): agent1"),
            ("spawn", ["a", "b", "c"], None, "Spawning 3 sub-agent(s): a, b, c"),
            ("spawn", None, None, "Spawning sub-agents"),
            ("spawn", [], None, "Spawning sub-agents"),
            ("delegate", None, {"agent1": "task1"}, "Delegating 1 task(s) to: agent1"),
            (
                "delegate",
                None,
                {"a": "t1", "b": "t2"},
                "Delegating 2 task(s) to: a, b",
            ),
            ("delegate", None, None, "Delegating tasks"),
            ("delegate", None, {}, "Delegating tasks"),
            ("unknown", None, None, "Delegate"),
            (None, None, None, "Delegate"),
        ],
    )
    def test_basic_formatting(
        self,
        command: str | None,
        ids: list[str] | None,
        tasks: dict | None,
        expected: str,
    ):
        """Test basic title formatting for different command types."""
        result = format_delegate_title(command, ids=ids, tasks=tasks)
        assert result == expected


class TestSpawnTitleWithAgentTypes:
    """Tests for spawn title formatting with agent_types parameter."""

    def test_agent_types_included_when_flag_set(self):
        """Agent types are included in title when include_agent_types=True."""
        result = format_delegate_title(
            "spawn",
            ids=["agent1", "agent2"],
            agent_types=["researcher", "coder"],
            include_agent_types=True,
        )
        assert result == "Spawning 2 sub-agent(s): agent1 (researcher), agent2 (coder)"

    def test_agent_types_ignored_when_flag_not_set(self):
        """Agent types are ignored when include_agent_types=False (default)."""
        result = format_delegate_title(
            "spawn",
            ids=["agent1", "agent2"],
            agent_types=["researcher", "coder"],
            include_agent_types=False,
        )
        assert result == "Spawning 2 sub-agent(s): agent1, agent2"

    def test_default_agent_type_not_displayed(self):
        """Agent type 'default' is filtered out from display."""
        result = format_delegate_title(
            "spawn",
            ids=["agent1", "agent2"],
            agent_types=["default", "coder"],
            include_agent_types=True,
        )
        assert result == "Spawning 2 sub-agent(s): agent1, agent2 (coder)"

    def test_all_default_types_shows_no_types(self):
        """When all agent types are 'default', no types are shown."""
        result = format_delegate_title(
            "spawn",
            ids=["agent1", "agent2"],
            agent_types=["default", "default"],
            include_agent_types=True,
        )
        assert result == "Spawning 2 sub-agent(s): agent1, agent2"

    @pytest.mark.parametrize(
        "ids,agent_types,expected",
        [
            # Fewer types than ids - graceful handling
            (
                ["a", "b", "c"],
                ["type1"],
                "Spawning 3 sub-agent(s): a (type1), b, c",
            ),
            # Empty agent_types list
            (["a", "b"], [], "Spawning 2 sub-agent(s): a, b"),
            # None agent_types with flag set
            (["a", "b"], None, "Spawning 2 sub-agent(s): a, b"),
        ],
    )
    def test_mismatched_or_missing_agent_types(
        self, ids: list[str], agent_types: list[str] | None, expected: str
    ):
        """Handles cases where agent_types is shorter than ids or missing."""
        result = format_delegate_title(
            "spawn",
            ids=ids,
            agent_types=agent_types,
            include_agent_types=True,
        )
        assert result == expected
