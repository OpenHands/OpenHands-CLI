from __future__ import annotations

from unittest.mock import patch

import pytest

from openhands_cli.argparsers.main_parser import create_main_parser
from tests.conftest import MockLocations


def test_no_user_skills_flag_default_is_true():
    """Test that user_skills defaults to True when --no-user-skills is not provided."""
    parser = create_main_parser()
    args = parser.parse_args([])
    assert args.user_skills is True


def test_no_user_skills_flag_sets_false():
    """Test that --no-user-skills sets user_skills to False."""
    parser = create_main_parser()
    args = parser.parse_args(["--no-user-skills"])
    assert args.user_skills is False


class TestUserSkillsIntegration:
    """Integration tests that verify the --no-user-skills flag behavior end-to-end."""

    @pytest.fixture
    def user_skills_dir(self, mock_locations: MockLocations):
        """Create a user skills directory with a test skill."""
        user_skills_path = mock_locations.home_dir / ".openhands" / "skills"
        user_skills_path.mkdir(parents=True)

        # Create a user skill file
        user_skill = user_skills_path / "my_user_skill.md"
        user_skill.write_text("""---
name: my_user_skill
triggers: ["my-user-skill", "user skill test"]
---

This is a user skill that should only be loaded when user_skills=True.
""")
        return user_skills_path

    def test_user_skills_loaded_by_default(
        self, mock_locations: MockLocations, user_skills_dir, persisted_agent
    ):
        """Test that user skills are loaded when user_skills=True (default)."""
        mock_user_dirs = [user_skills_dir]

        with patch(
            "openhands.sdk.context.skills.skill.USER_SKILLS_DIRS", mock_user_dirs
        ):
            from openhands_cli.stores import AgentStore

            agent_store = AgentStore()
            loaded_agent = agent_store.load_or_create(user_skills=True)

            assert loaded_agent is not None
            assert loaded_agent.agent_context is not None

            # Verify user skill is included
            skill_names = [skill.name for skill in loaded_agent.agent_context.skills]
            assert "my_user_skill" in skill_names

    def test_user_skills_not_loaded_when_disabled(
        self, mock_locations: MockLocations, user_skills_dir, persisted_agent
    ):
        """Test that user skills are NOT loaded when user_skills=False."""
        mock_user_dirs = [user_skills_dir]

        with patch(
            "openhands.sdk.context.skills.skill.USER_SKILLS_DIRS", mock_user_dirs
        ):
            from openhands_cli.stores import AgentStore

            agent_store = AgentStore()
            loaded_agent = agent_store.load_or_create(user_skills=False)

            assert loaded_agent is not None
            assert loaded_agent.agent_context is not None

            # Verify user skill is NOT included
            skill_names = [skill.name for skill in loaded_agent.agent_context.skills]
            assert "my_user_skill" not in skill_names

    def test_agent_context_load_user_skills_parameter(
        self, mock_locations: MockLocations, persisted_agent
    ):
        """Test that AgentContext is created with correct load_user_skills parameter."""
        from openhands_cli.stores import AgentStore

        agent_store = AgentStore()

        # Test with user_skills=True
        agent_with_user_skills = agent_store.load_or_create(user_skills=True)
        assert agent_with_user_skills is not None
        assert agent_with_user_skills.agent_context is not None
        assert agent_with_user_skills.agent_context.load_user_skills is True

        # Test with user_skills=False
        agent_without_user_skills = agent_store.load_or_create(user_skills=False)
        assert agent_without_user_skills is not None
        assert agent_without_user_skills.agent_context is not None
        assert agent_without_user_skills.agent_context.load_user_skills is False
