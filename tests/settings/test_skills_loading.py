"""Unit tests for skills loading functionality in AgentStore."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with skills."""
    with tempfile.TemporaryDirectory() as temp_dir:
        skills_dir = Path(temp_dir) / ".openhands" / "skills"
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

        yield temp_dir


@pytest.fixture
def agent_store(temp_project_dir):
    """Create an AgentStore with the temporary project directory."""
    with patch("openhands_cli.stores.agent_store.WORK_DIR", temp_project_dir):
        from openhands_cli.stores import AgentStore

        yield AgentStore()


class TestSkillsLoading:
    """Test skills loading functionality with actual project skills."""

    def test_load_agent_with_project_skills(self, agent_store):
        """Test that loading agent includes skills from project directories."""
        from openhands.sdk import LLM, Agent

        # Create a test agent to save first
        test_agent = Agent(llm=LLM(model="gpt-4o-mini"))
        agent_store.save(test_agent)

        # Load agent - this should include skills from project directories
        loaded_agent = agent_store.load()

        assert loaded_agent is not None
        assert loaded_agent.agent_context is not None

        # Verify that project skills were loaded into the agent context
        # Should have exactly 3 project skills from .openhands/skills
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

    def test_load_agent_with_user_and_project_skills_combined(self, temp_project_dir):
        """Test that user and project skills are properly combined.

        This test verifies that when loading an agent, both user and project skills
        are properly loaded and combined.
        """
        # Create temporary user directories
        import tempfile

        from openhands.sdk import LLM, Agent

        with tempfile.TemporaryDirectory() as user_temp_dir:
            user_skills_temp = Path(user_temp_dir) / ".openhands" / "skills"
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
                "openhands.sdk.context.skills.skill.USER_SKILLS_DIRS", mock_user_dirs
            ):
                with patch(
                    "openhands_cli.stores.agent_store.WORK_DIR", temp_project_dir
                ):
                    # Create a minimal agent configuration for testing
                    from openhands_cli.stores import AgentStore

                    agent_store = AgentStore()

                    # Create a test agent to save first
                    test_agent = Agent(llm=LLM(model="gpt-4o-mini"))
                    agent_store.save(test_agent)

                    loaded_agent = agent_store.load()
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

    def test_load_agent_with_public_skills(self, temp_project_dir):
        """Test that loading agent includes public skills from the OpenHands repository.

        This test verifies that when an agent is loaded with load_public_skills=True,
        public skills from https://github.com/OpenHands/skills are loaded.
        """
        from unittest.mock import patch

        from openhands.sdk import LLM, Agent
        from openhands.sdk.context.skills import Skill

        # Mock public skills - simulate loading from GitHub repo
        mock_public_skill = Skill(
            name="github",
            content="This is a public skill about GitHub.",
            trigger=None,
        )

        with (
            patch("openhands_cli.stores.agent_store.WORK_DIR", temp_project_dir),
            patch(
                "openhands.sdk.context.agent_context.load_public_skills"
            ) as mock_load_public,
        ):
            # Mock load_public_skills to return our test skill
            mock_load_public.return_value = [mock_public_skill]

            from openhands_cli.stores import AgentStore

            agent_store = AgentStore()

            # Create a test agent to save first
            test_agent = Agent(llm=LLM(model="gpt-4o-mini"))
            agent_store.save(test_agent)

            # Load agent - this should include public skills
            loaded_agent = agent_store.load()

            assert loaded_agent is not None
            assert loaded_agent.agent_context is not None

            # Verify load_public_skills was called
            mock_load_public.assert_called_once()

            # Verify that the agent context has load_public_skills enabled
            # Note: We can't directly check this as it's processed during initialization
            # But we can verify that our mocked public skill is in the skills list
            all_skills = loaded_agent.agent_context.skills
            skill_names = [skill.name for skill in all_skills]

            # Should have project skills + mocked public skill
            assert "github" in skill_names  # mocked public skill
