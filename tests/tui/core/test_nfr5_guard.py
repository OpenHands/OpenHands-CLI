"""NFR-5 guard: forbid list(state.events) materialization in replay-related files.

This test enforces the v0.04 non-functional requirement that replay code must
never eagerly materialise the full event list via ``list(state.events)`` or
``list(self.conversation.state.events)``.  The windowed/lazy replay cascade
should be the only access path.
"""

import re
from pathlib import Path

import pytest

# Files covered by the guard (relative to repo root)
_GUARDED_FILES = [
    "openhands_cli/tui/core/conversation_runner.py",
    "openhands_cli/tui/widgets/richlog_visualizer.py",
    "openhands_cli/tui/core/conversation_manager.py",
]

_FORBIDDEN_PATTERN = re.compile(r"\blist\s*\(\s*(?:self\.conversation\.)?state\.events\s*\)")

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("rel_path", _GUARDED_FILES, ids=lambda p: p.split("/")[-1])
def test_no_list_state_events_materialisation(rel_path: str) -> None:
    """Grep guard: replay files must not contain list(*.events) calls."""
    source = (_REPO_ROOT / rel_path).read_text()
    matches = _FORBIDDEN_PATTERN.findall(source)
    assert not matches, (
        f"NFR-5 violation in {rel_path}: found forbidden pattern(s) {matches}. "
        "Use windowed/lazy replay instead of materialising full event list."
    )
