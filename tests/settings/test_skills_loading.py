"""Unit tests for skills loading functionality in AgentStore."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from openhands_cli.tui.settings.store import AgentStore


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
def agent_store(temp_project_dir):
    """Create an AgentStore with the temporary project directory."""
    with patch("openhands_cli.tui.settings.store.WORK_DIR", temp_project_dir):
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
        all_skills = loaded_agent.agent_context.skills
        assert isinstance(all_skills, list)
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
                    "openhands_cli.tui.settings.store.WORK_DIR", temp_project_dir
                ):
                    # Create a minimal agent configuration for testing
                    agent_store = AgentStore()

                    # Create a test agent to save first
                    test_agent = Agent(llm=LLM(model="gpt-4o-mini"))
                    agent_store.save(test_agent)

                    loaded_agent = agent_store.load()
                    assert loaded_agent is not None
                    assert loaded_agent.agent_context is not None

                    # Project skills: 3 (2 microagents + 1 skill)
                    # User skills: 2 (1 skill + 1 microagent)
                    all_skills = loaded_agent.agent_context.skills
                    assert isinstance(all_skills, list)
                    assert len(all_skills) == 5

                    # Verify we have skills from both sources
                    skill_names = [skill.name for skill in all_skills]
                    assert "test_skill" in skill_names  # project skill
                    assert "test_microagent" in skill_names  # project microagent
                    assert "integration_test" in skill_names  # project microagent
                    assert "user_skill" in skill_names  # user skill
                    assert "user_microagent" in skill_names  # user microagent


@pytest.fixture
def temp_project_dir_with_context_files():
    """Create a temporary project directory with CLAUDE.md and GEMINI.md files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create .openhands/skills directory
        skills_dir = Path(temp_dir) / ".openhands" / "skills"
        skills_dir.mkdir(parents=True)

        # Add a dummy skill file so the directory is processed
        # (empty directories might be skipped)
        dummy_skill = skills_dir / "dummy.md"
        dummy_skill.write_text("""---
name: dummy_skill
---

This is a dummy skill to ensure the directory is processed.""")

        # Create claude.md in project root (lowercase to match SDK pattern)
        claude_file = Path(temp_dir) / "claude.md"
        claude_file.write_text("""# Claude-Specific Instructions

These are instructions for Claude AI to follow when working on this project.""")

        # Create gemini.md in project root (lowercase to match SDK pattern)
        gemini_file = Path(temp_dir) / "gemini.md"
        gemini_file.write_text("""# Gemini-Specific Instructions

These are instructions for Google Gemini AI to follow when working on this project.""")

        # Create AGENTS.MD in project root (uppercase extension to test that existing functionality still works)
        agents_file = Path(temp_dir) / "AGENTS.MD"
        agents_file.write_text("""# General Agent Instructions

These are general instructions for all agents working on this project.""")

        yield temp_dir


def test_load_repo_context_files(temp_project_dir_with_context_files):
    """Test that CLAUDE.md, GEMINI.md, and AGENTS.md are loaded from project root."""
    from openhands.sdk import LLM, Agent

    with patch("openhands_cli.tui.settings.store.WORK_DIR", temp_project_dir_with_context_files):
        agent_store = AgentStore()

        # Create and save a test agent
        test_agent = Agent(llm=LLM(model="gpt-4o-mini"))
        agent_store.save(test_agent)

        # Load agent - this should include context files from project root
        loaded_agent = agent_store.load()

        assert loaded_agent is not None
        assert loaded_agent.agent_context is not None

        # Verify that context files were loaded as skills
        all_skills = loaded_agent.agent_context.skills
        skill_names = [skill.name for skill in all_skills]

        # All three context files should be loaded
        assert "claude" in skill_names
        assert "gemini" in skill_names
        assert "agents" in skill_names

        # Verify the content of each context file
        claude_skill = next(s for s in all_skills if s.name == "claude")
        assert "Claude-Specific Instructions" in claude_skill.content
        assert claude_skill.trigger is None  # Should be always-active

        gemini_skill = next(s for s in all_skills if s.name == "gemini")
        assert "Gemini-Specific Instructions" in gemini_skill.content
        assert gemini_skill.trigger is None  # Should be always-active

        agents_skill = next(s for s in all_skills if s.name == "agents")
        assert "General Agent Instructions" in agents_skill.content
        assert agents_skill.trigger is None  # Should be always-active


@pytest.fixture
def temp_project_dir_with_large_context_file():
    """Create a temporary project directory with a very large CLAUDE.md file to test truncation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir)
        
        # Create .openhands/skills directory
        skills_dir = project_dir / ".openhands" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        # Add a dummy skill file
        dummy_skill = skills_dir / "dummy.md"
        dummy_skill.write_text("""---
name: dummy_skill
version: 1.0.0
agent: CodeActAgent
---

# Dummy Skill

Dummy skill content.
""")

        # Create a very large claude.md file (15,000 chars, exceeds 10,000 limit)
        # Use lowercase to match SDK pattern
        claude_content = "# Claude Instructions - Start\n\n"
        for i in range(800):  # This will create ~15,000+ characters
            claude_content += f"Claude instruction line {i:04d}: Follow this guideline carefully.\n"
        claude_content += "\n# Claude Instructions - End\n"
        
        (project_dir / "claude.md").write_text(claude_content)
        original_size = len(claude_content)

        # Create a normal-sized gemini.md file (lowercase to match SDK pattern)
        gemini_content = """# Gemini-Specific Instructions

These are Gemini-specific instructions for the agent.
"""
        (project_dir / "gemini.md").write_text(gemini_content)

        yield project_dir, original_size


def test_load_repo_context_files_with_truncation(temp_project_dir_with_large_context_file):
    """Test that large repo context files are truncated properly."""
    from openhands.sdk import LLM, Agent
    from openhands.sdk.context.skills.skill import THIRD_PARTY_SKILL_MAX_CHARS
    
    project_dir, original_size = temp_project_dir_with_large_context_file

    with patch("openhands_cli.tui.settings.store.WORK_DIR", project_dir):
        agent_store = AgentStore()

        # Create and save a test agent
        test_agent = Agent(llm=LLM(model="gpt-4o-mini"))
        agent_store.save(test_agent)

        # Load agent - this should include context files from project root
        loaded_agent = agent_store.load()

        assert loaded_agent is not None
        assert loaded_agent.agent_context is not None

        # Verify skills were loaded
        all_skills = loaded_agent.agent_context.skills
        skill_names = [skill.name for skill in all_skills]

        # Both context files should be loaded
        assert "claude" in skill_names
        assert "gemini" in skill_names

        # Check CLAUDE.md was truncated
        claude_skill = next(s for s in all_skills if s.name == "claude")
        assert claude_skill.trigger is None  # Should be always-active
        
        # Content should be truncated
        assert len(claude_skill.content) <= THIRD_PARTY_SKILL_MAX_CHARS
        assert original_size > THIRD_PARTY_SKILL_MAX_CHARS
        
        # Should contain the truncation notice with filepath
        assert "<TRUNCATED>" in claude_skill.content
        assert "exceeded the maximum length" in claude_skill.content
        assert "claude.md" in claude_skill.content  # Should mention the filename
        assert "You can read the full file if needed" in claude_skill.content
        
        # Should preserve beginning and end
        assert "Claude Instructions - Start" in claude_skill.content
        assert "Claude Instructions - End" in claude_skill.content

        # Check GEMINI.md was NOT truncated (it's small)
        gemini_skill = next(s for s in all_skills if s.name == "gemini")
        assert gemini_skill.trigger is None  # Should be always-active
        assert "<TRUNCATED>" not in gemini_skill.content
        assert "Gemini-Specific Instructions" in gemini_skill.content
