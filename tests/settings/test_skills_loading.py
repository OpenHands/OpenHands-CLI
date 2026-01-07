"""Unit tests for skills loading functionality in AgentStore."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with microagents."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create microagents directory with actual files
        microagents_dir = Path(temp_dir) / ".openhands" / "microagents"
        microagents_dir.mkdir(parents=True)

        # Create test microagent files
        microagent1 = microagents_dir / "test_microagent.md"
        microagent1.write_text("""---
name: test_microagent
triggers: ["test", "microagent"]
---

This is a test microagent for testing purposes.
""")

        microagent2 = microagents_dir / "integration_test.md"
        microagent2.write_text("""---
name: integration_test
triggers: ["integration", "test"]
---

This microagent is used for integration testing.
""")

        # Also create skills directory
        skills_dir = Path(temp_dir) / ".openhands" / "skills"
        skills_dir.mkdir(parents=True)

        skill_file = skills_dir / "test_skill.md"
        skill_file.write_text("""---
name: test_skill
triggers: ["test", "skill"]
---

This is a test skill for testing purposes.
""")

        yield temp_dir


@pytest.fixture
def temp_project_dir_with_agents_md_only():
    """Create a temporary project directory with only AGENTS.md (no skills dirs)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create AGENTS.md file in the root directory (no .openhands/skills)
        agents_md = Path(temp_dir) / "AGENTS.md"
        agents_md.write_text("""# Project Guidelines

This is the AGENTS.md file with project-specific instructions.

## Code Style
- Use consistent formatting
- Write clear comments

## Testing
- Always write tests for new features
""")

        yield temp_dir


@pytest.fixture
def temp_project_dir_with_agents_md_and_skills():
    """Create a temporary project directory with both AGENTS.md and skills dirs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create AGENTS.md file in the root directory
        agents_md = Path(temp_dir) / "AGENTS.md"
        agents_md.write_text("""# Project Guidelines

This is the AGENTS.md file with project-specific instructions.
""")

        # Also create skills directory with a skill
        skills_dir = Path(temp_dir) / ".openhands" / "skills"
        skills_dir.mkdir(parents=True)

        skill_file = skills_dir / "test_skill.md"
        skill_file.write_text("""---
name: test_skill
triggers: ["test", "skill"]
---

This is a test skill for testing purposes.
""")

        yield temp_dir


@pytest.fixture
def agent_store(temp_project_dir):
    """Create an AgentStore with the temporary project directory."""
    with patch("openhands_cli.stores.agent_store.WORK_DIR", temp_project_dir):
        from openhands_cli.stores import AgentStore

        yield AgentStore()


class TestSkillsLoading:
    """Test skills loading functionality with actual microagents."""

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
        # Should have exactly 3 project skills: 2 microagents + 1 skill
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
            user_microagents_temp = Path(user_temp_dir) / ".openhands" / "microagents"
            user_skills_temp.mkdir(parents=True)
            user_microagents_temp.mkdir(parents=True)

            # Create user skill files
            user_skill = user_skills_temp / "user_skill.md"
            user_skill.write_text("""---
name: user_skill
triggers: ["user", "skill"]
---

This is a user skill for testing.
""")

            user_microagent = user_microagents_temp / "user_microagent.md"
            user_microagent.write_text("""---
name: user_microagent
triggers: ["user", "microagent"]
---

This is a user microagent for testing.
""")

            # Mock the USER_SKILLS_DIRS constant to point to our temp directories
            mock_user_dirs = [user_skills_temp, user_microagents_temp]

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

                    # Project skills: 3 (2 microagents + 1 skill)
                    # User skills: 2 (1 skill + 1 microagent)
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


class TestThirdPartySkillsLoading:
    """Test loading of third-party skill files (AGENTS.md, etc.)."""

    def test_load_agents_md_without_skills_directory(
        self, temp_project_dir_with_agents_md_only
    ):
        """Test that AGENTS.md is loaded even when .openhands/skills doesn't exist.

        This is the main bug fix test - verifies that third-party skill files
        like AGENTS.md are loaded from the work directory even when the
        .openhands/skills directory doesn't exist.
        """
        from openhands.sdk import LLM, Agent

        with patch(
            "openhands_cli.stores.agent_store.WORK_DIR",
            temp_project_dir_with_agents_md_only,
        ):
            from openhands_cli.stores import AgentStore

            agent_store = AgentStore()

            # Create a test agent to save first
            test_agent = Agent(llm=LLM(model="gpt-4o-mini"))
            agent_store.save(test_agent)

            # Load agent - this should include AGENTS.md even without skills dir
            loaded_agent = agent_store.load()

            assert loaded_agent is not None
            assert loaded_agent.agent_context is not None

            # Verify that AGENTS.md was loaded as a skill
            all_skills = loaded_agent.agent_context.skills
            skill_names = [skill.name for skill in all_skills]

            # The "agents" skill should be present (from AGENTS.md)
            assert "agents" in skill_names, (
                f"AGENTS.md should be loaded as 'agents' skill. "
                f"Found skills: {skill_names}"
            )

            # Verify the content is correct
            agents_skill = next(s for s in all_skills if s.name == "agents")
            assert "Project Guidelines" in agents_skill.content
            assert agents_skill.trigger is None  # Third-party skills are always active

    def test_load_agents_md_with_skills_directory(
        self, temp_project_dir_with_agents_md_and_skills
    ):
        """Test that AGENTS.md is loaded alongside skills from .openhands/skills.

        Verifies that when both AGENTS.md and .openhands/skills exist,
        both are loaded without duplicates.
        """
        from openhands.sdk import LLM, Agent

        with patch(
            "openhands_cli.stores.agent_store.WORK_DIR",
            temp_project_dir_with_agents_md_and_skills,
        ):
            from openhands_cli.stores import AgentStore

            agent_store = AgentStore()

            # Create a test agent to save first
            test_agent = Agent(llm=LLM(model="gpt-4o-mini"))
            agent_store.save(test_agent)

            # Load agent
            loaded_agent = agent_store.load()

            assert loaded_agent is not None
            assert loaded_agent.agent_context is not None

            all_skills = loaded_agent.agent_context.skills
            skill_names = [skill.name for skill in all_skills]

            # Both AGENTS.md and the skill from .openhands/skills should be loaded
            assert "agents" in skill_names, (
                f"AGENTS.md should be loaded. Found skills: {skill_names}"
            )
            assert "test_skill" in skill_names, (
                f"test_skill should be loaded. Found skills: {skill_names}"
            )

    def test_load_third_party_skills_function_directly(
        self, temp_project_dir_with_agents_md_only
    ):
        """Test the load_third_party_skills_from_work_dir function directly."""
        from openhands_cli.stores.agent_store import (
            load_third_party_skills_from_work_dir,
        )

        skills = load_third_party_skills_from_work_dir(
            temp_project_dir_with_agents_md_only
        )

        assert len(skills) == 1
        assert skills[0].name == "agents"
        assert "Project Guidelines" in skills[0].content
        assert skills[0].trigger is None

    def test_load_third_party_skills_empty_directory(self):
        """Test that function returns empty list for empty directory."""
        from openhands_cli.stores.agent_store import (
            load_third_party_skills_from_work_dir,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            skills = load_third_party_skills_from_work_dir(temp_dir)
            assert skills == []

    def test_load_third_party_skills_case_insensitive(self):
        """Test that third-party skill files are loaded case-insensitively."""
        from openhands_cli.stores.agent_store import (
            load_third_party_skills_from_work_dir,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create agents.md (lowercase)
            agents_md = Path(temp_dir) / "agents.md"
            agents_md.write_text("# Lowercase agents.md content")

            skills = load_third_party_skills_from_work_dir(temp_dir)

            assert len(skills) == 1
            assert skills[0].name == "agents"

    def test_load_multiple_third_party_files(self):
        """Test loading multiple third-party skill files."""
        from openhands_cli.stores.agent_store import (
            load_third_party_skills_from_work_dir,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create AGENTS.md
            agents_md = Path(temp_dir) / "AGENTS.md"
            agents_md.write_text("# AGENTS.md content")

            # Create .cursorrules
            cursorrules = Path(temp_dir) / ".cursorrules"
            cursorrules.write_text("# Cursor rules content")

            skills = load_third_party_skills_from_work_dir(temp_dir)

            assert len(skills) == 2
            skill_names = [s.name for s in skills]
            assert "agents" in skill_names
            assert "cursorrules" in skill_names
