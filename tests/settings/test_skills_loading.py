"""Unit tests for skills loading functionality in AgentStore."""

from unittest.mock import patch

import pytest

from tests.conftest import MockLocations


@pytest.fixture
def temp_project_dir(mock_locations: MockLocations):
    """Create a temporary project directory with skills."""
    work_dir = mock_locations.work_dir
    skills_dir = work_dir / ".openhands" / "skills"
    skills_dir.mkdir(parents=True)

    # Create test skill files
    skill_file = skills_dir / "test_skill.md"
    skill_file.write_text("""---
name: test_skill
triggers: ["test", "skill"]
---

This is a test skill for testing purposes.
""")

    # Create additional skill-like files (previously stored under
    # .openhands/microagents)
    microagent1 = skills_dir / "test_microagent.md"
    microagent1.write_text("""---
name: test_microagent
triggers: ["test", "microagent"]
---

This is a test microagent for testing purposes.
""")

    microagent2 = skills_dir / "integration_test.md"
    microagent2.write_text("""---
name: integration_test
triggers: ["integration", "test"]
---

This microagent is used for integration testing.
""")

    return str(work_dir)


@pytest.fixture
def agent_store(temp_project_dir):
    """Create an AgentStore with the temporary project directory."""
    from openhands_cli.stores import AgentStore

    return AgentStore()


class TestSkillsLoading:
    """Test skills loading functionality with actual project skills."""

    def test_load_agent_with_project_skills(self, agent_store, persisted_agent):
        """Test that loading agent includes skills from project directories."""

        # Load agent - this should include skills from project directories
        loaded_agent = agent_store.load_or_create()

        assert loaded_agent is not None
        assert loaded_agent.agent_context is not None

        # Verify that project skills were loaded into the agent context
        # Should have exactly 3 project skills from .agents/skills
        # Plus any user skills that might be loaded via load_user_skills=True
        # Plus public skills from the GitHub repository
        all_skills = loaded_agent.agent_context.skills
        assert isinstance(all_skills, list)
        # Should have at least the 3 project skills
        assert len(all_skills) >= 3

        # Verify we have the expected project skills
        skill_names = [skill.name for skill in all_skills]
        assert "test_skill" in skill_names  # project skill
        assert "test_microagent" in skill_names  # project microagent
        assert "integration_test" in skill_names  # project microagent

    def test_load_agent_with_user_and_project_skills_combined(
        self, temp_project_dir, mock_locations, persisted_agent
    ):
        """Test that user and project skills are properly combined.

        This test verifies that when loading an agent, both user and project skills
        are properly loaded and combined.
        """
        # Create user skills in mock_locations.home_dir
        user_skills_temp = mock_locations.home_dir / ".openhands" / "skills"
        user_skills_temp.mkdir(parents=True)

        # Create user skill files
        user_skill = user_skills_temp / "user_skill.md"
        user_skill.write_text("""---
name: user_skill
triggers: ["user", "skill"]
---

This is a user skill for testing.
""")

        user_microagent = user_skills_temp / "user_microagent.md"
        user_microagent.write_text("""---
name: user_microagent
triggers: ["user", "microagent"]
---

This is a user microagent for testing.
""")

        # Mock the USER_SKILLS_DIRS constant to point to our temp directory
        mock_user_dirs = [user_skills_temp]

        with patch(
            "openhands.sdk.skills.skill.USER_SKILLS_DIRS", mock_user_dirs
        ):
            from openhands_cli.stores import AgentStore

            agent_store = AgentStore()

            loaded_agent = agent_store.load_or_create()
            assert loaded_agent is not None
            assert loaded_agent.agent_context is not None

            # Project skills: 3
            # User skills: 2
            # Public skills: loaded from GitHub repository (variable count)
            all_skills = loaded_agent.agent_context.skills
            assert isinstance(all_skills, list)
            # Should have at least project + user skills (5)
            assert len(all_skills) >= 5

            # Verify we have skills from both sources
            skill_names = [skill.name for skill in all_skills]
            assert "test_skill" in skill_names  # project skill
            assert "test_microagent" in skill_names  # project microagent
            assert "integration_test" in skill_names  # project microagent
            assert "user_skill" in skill_names  # user skill
            assert "user_microagent" in skill_names  # user microagent

    def test_build_agent_context_enables_sdk_managed_skill_loading(
        self, temp_project_dir
    ):
        """Test that AgentStore enables SDK-managed user and public skill loading.

        This verifies the CLI-specific contract: AgentStore builds an AgentContext
        with project skills plus the flags that tell the SDK to auto-load user and
        public skills.
        """
        from openhands_cli.stores import AgentStore

        class FakeAgentContext:
            def __init__(self, **kwargs):
                self.skills = kwargs["skills"]
                self.system_message_suffix = kwargs["system_message_suffix"]
                self.load_user_skills = kwargs["load_user_skills"]
                self.load_public_skills = kwargs["load_public_skills"]

        with (
            patch("openhands_cli.stores.agent_store.AgentContext", FakeAgentContext),
            patch(
                "openhands_cli.stores.agent_store.get_work_dir",
                return_value=temp_project_dir,
            ),
            patch(
                "openhands_cli.stores.agent_store.get_os_description",
                return_value="TestOS 1.0",
            ),
        ):
            agent_store = AgentStore()
            agent_context = agent_store._build_agent_context()

        assert isinstance(agent_context, FakeAgentContext)
        assert agent_context.load_user_skills is True
        assert agent_context.load_public_skills is True

        skill_names = [skill.name for skill in agent_context.skills]
        assert "test_skill" in skill_names
        assert "test_microagent" in skill_names
        assert "integration_test" in skill_names
        assert agent_context.system_message_suffix == (
            f"Your current working directory is: {temp_project_dir}\n"
            "User operating system: TestOS 1.0"
        )
