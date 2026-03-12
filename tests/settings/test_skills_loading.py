"""Unit tests for skills loading functionality in AgentStore."""

from unittest.mock import patch

import pytest

from tests.conftest import MockLocations


# ============================================================================
# UnicodeDecodeError recovery
# ============================================================================


class TestAgentStoreBuildContextUnicodeError:
    """_build_agent_context must tolerate UnicodeDecodeError from load_project_skills.

    AGENTS.md or any skill file may contain non-UTF-8 bytes (e.g., Latin-1
    text or binary data).  A crash here blocks the entire session; we should
    warn and continue with an empty project-skill list instead.
    """

    def _common_patches(self, mock_locations: MockLocations, unicode_exc: Exception):
        """Return nested patches shared by both tests."""
        return (
            patch(
                "openhands_cli.stores.agent_store.load_project_skills",
                side_effect=unicode_exc,
            ),
            patch(
                "openhands_cli.stores.agent_store.get_work_dir",
                return_value=str(mock_locations.work_dir),
            ),
            patch(
                "openhands_cli.stores.agent_store.get_os_description",
                return_value="Linux",
            ),
            # Prevent public/user skill loading so context.skills stays minimal
            patch(
                "openhands.sdk.context.agent_context.load_public_skills",
                return_value=[],
            ),
            patch(
                "openhands.sdk.context.agent_context.load_user_skills",
                return_value=[],
            ),
        )

    def test_unicode_error_falls_back_to_empty_skills(
        self, mock_locations: MockLocations
    ):
        """UnicodeDecodeError from load_project_skills must not crash the session."""
        unicode_exc = UnicodeDecodeError("utf-8", b"\xd1", 0, 1, "invalid start byte")

        patches = self._common_patches(mock_locations, unicode_exc)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            from openhands_cli.stores import AgentStore

            store = AgentStore()
            context = store._build_agent_context()

        assert context.skills == [], (
            "_build_agent_context should pass an empty project-skill list when "
            "load_project_skills raises UnicodeDecodeError"
        )

    def test_unicode_error_prints_warning_to_stderr(
        self, mock_locations: MockLocations, capsys
    ):
        """A human-readable warning must be printed to stderr on UnicodeDecodeError."""
        unicode_exc = UnicodeDecodeError("utf-8", b"\xd1", 4, 5, "invalid start byte")

        patches = self._common_patches(mock_locations, unicode_exc)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            from openhands_cli.stores import AgentStore

            store = AgentStore()
            store._build_agent_context()

        captured = capsys.readouterr()
        # Rich prints to stderr; check the combined output for the key message
        output = captured.out + captured.err
        assert "Warning" in output or "UTF-8" in output, (
            f"Expected a warning message about the encoding error, but got: {output!r}"
        )


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
            "openhands.sdk.context.skills.skill.USER_SKILLS_DIRS", mock_user_dirs
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

    def test_load_agent_with_public_skills(self, temp_project_dir, persisted_agent):
        """Test that loading agent includes public skills from the OpenHands repository.

        This test verifies that when an agent is loaded with load_public_skills=True,
        public skills from https://github.com/OpenHands/extensions are loaded.
        """
        from openhands.sdk.context.skills import Skill

        # Mock public skills - simulate loading from GitHub repo
        mock_public_skill = Skill(
            name="github",
            content="This is a public skill about GitHub.",
            trigger=None,
        )

        with patch(
            "openhands.sdk.context.agent_context.load_public_skills"
        ) as mock_load_public:
            # Mock load_public_skills to return our test skill
            mock_load_public.return_value = [mock_public_skill]

            from openhands_cli.stores import AgentStore

            agent_store = AgentStore()

            # Load agent - this should include public skills
            loaded_agent = agent_store.load_or_create()

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
