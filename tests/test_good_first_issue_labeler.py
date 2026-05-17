"""Tests for .github/scripts/good-first-issue-labeler.py"""

import importlib.util
from pathlib import Path

import pytest


_SCRIPT = Path(__file__).parent.parent / ".github/scripts/good_first_issue_labeler.py"


@pytest.fixture(scope="module")
def labeler():
    spec = importlib.util.spec_from_file_location("good_first_issue_labeler", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_load_prompt_from_default_repo_root(labeler):
    """_load_prompt must succeed using the default _REPO_ROOT."""
    prompt = labeler._load_prompt(labeler._REPO_ROOT)
    assert prompt.strip()


@pytest.mark.parametrize(
    "method,endpoint,expected",
    [
        # Allowed — every operation the prompt requires
        ("GET", "/search/issues", True),
        ("GET", "/repos/OpenHands/OpenHands-CLI/issues", True),
        ("GET", "/repos/OpenHands/OpenHands-CLI/issues/42", True),
        ("GET", "/repos/OpenHands/OpenHands-CLI/labels", True),
        ("POST", "/repos/OpenHands/OpenHands-CLI/labels", True),
        ("POST", "/repos/OpenHands/OpenHands-CLI/issues/42/labels", True),
        # Blocked — mutating or out-of-scope operations
        ("DELETE", "/repos/OpenHands/OpenHands-CLI/issues/42", False),
        ("PATCH", "/repos/OpenHands/OpenHands-CLI/issues/42", False),
        ("POST", "/repos/OpenHands/OpenHands-CLI/issues/42/comments", False),
        ("GET", "/repos/OpenHands/OpenHands-CLI/git/refs", False),
        ("DELETE", "/repos/OpenHands/OpenHands-CLI/labels/good+first", False),
        # Blocked — multi-segment paths that fnmatch '*' would have matched
        ("GET", "/repos/OpenHands/OpenHands-CLI/issues/42/comments", False),
        ("POST", "/repos/OpenHands/OpenHands-CLI/issues/42/extra/labels", False),
    ],
)
def test_is_allowed(labeler, method, endpoint, expected):
    assert labeler._is_allowed(method, endpoint) is expected
