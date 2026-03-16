"""E2E snapshot test for /skills command.

This test validates the /skills command flow:
1. User types "/skills"
2. The loaded resources (skills, hooks, MCPs) are displayed
"""

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from textual.pilot import Pilot

from .conftest import WORK_DIR
from .helpers import type_text, wait_for_app_ready, wait_for_idle


def _create_test_skills(work_dir: Path) -> None:
    """Create test skill files in the work directory.

    Creates skills in .openhands/skills/ directory following the
    OpenHands skill format with frontmatter.
    """
    skills_dir = work_dir / ".openhands" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Create a simple skill file with frontmatter
    skill1_content = """---
trigger: keyword
keywords:
  - test
  - example
---
# Test Skill

This is a test skill for e2e testing.

When the user mentions "test" or "example", provide helpful guidance.
"""
    (skills_dir / "test-skill.md").write_text(skill1_content)

    # Create another skill without trigger (repo skill)
    skill2_content = """---
name: project-guidelines
---
# Project Guidelines

This skill provides project-specific guidelines and conventions.

## Code Style
- Use consistent formatting
- Write clear comments
"""
    (skills_dir / "project-guidelines.md").write_text(skill2_content)


@pytest.fixture
def mock_llm_with_skills(
    e2e_test_environment, mock_llm_setup
) -> Generator[dict[str, Any], None, None]:
    """Fixture that sets up mock LLM server with test skills.

    This fixture extends mock_llm_setup by also creating test skill files
    in the work directory so that the /skills command has skills to display.
    """
    # Create test skills in the work directory
    _create_test_skills(WORK_DIR)

    yield mock_llm_setup


class TestSkillsCommand:
    """Test /skills command."""

    def test_skills_command_with_skills(self, snap_compare, mock_llm_with_skills):
        """Test /skills command displays loaded skills.

        This test:
        1. Sets up test skills in the work directory
        2. Starts the real OpenHandsApp
        3. Types "/skills" in the input
        4. Presses Enter to select from dropdown
        5. Presses Enter again to execute the command
        6. Captures snapshot showing the loaded skills
        """
        # Lazy import AFTER fixture has patched locations
        from openhands.sdk.security.confirmation_policy import NeverConfirm
        from openhands_cli.tui.textual_app import OpenHandsApp

        async def run_skills_command(pilot: Pilot):
            """Simulate user typing and executing /skills command."""
            # Wait for app to fully initialize
            await wait_for_app_ready(pilot)

            # Type the command
            await type_text(pilot, "/skills")

            # First enter selects from dropdown, second enter executes /skills
            await pilot.press("enter")
            await pilot.press("enter")

            # Wait for all animations to complete
            await wait_for_idle(pilot)

        # Use fixed conversation ID from fixture for deterministic snapshots
        app = OpenHandsApp(
            exit_confirmation=False,
            initial_confirmation_policy=NeverConfirm(),
            resume_conversation_id=mock_llm_with_skills["conversation_id"],
        )

        assert snap_compare(
            app,
            terminal_size=(120, 40),
            run_before=run_skills_command,
        )
