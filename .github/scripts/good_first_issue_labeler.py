#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "openhands-sdk",
#   "httpx",
# ]
# ///
"""Agent that applies the 'good first issue' label to qualifying GitHub issues.

The agent follows the rules in .github/prompts/good-first-issue-labeler.md.
Tools: a whitelisted GitHub REST API tool, GlobTool, and PlanningFileEditorTool.

Usage
-----
    uv run .github/scripts/good_first_issue_labeler.py

Required environment variables
-------------------------------
    GITHUB_TOKEN   GitHub personal access token with repo label-write permissions
    LLM_API_KEY    API key for the LLM provider

Optional environment variables
--------------------------------
    LLM_MODEL      LiteLLM model string  (default: anthropic/claude-sonnet-4-5-20250929)
    LLM_BASE_URL   Override base URL for the LLM provider
"""

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx
from pydantic import Field

from openhands.sdk import (
    LLM,
    Action,
    Agent,
    Conversation,
    ImageContent,
    Observation,
    TextContent,
    ToolDefinition,
)
from openhands.sdk.tool import Tool, ToolAnnotations, ToolExecutor, register_tool
from openhands.tools.glob import GlobTool
from openhands.tools.planning_file_editor import PlanningFileEditorTool


_REPO_ROOT = Path(__file__).parent.parent.parent


# =============================================================================
# Tool 1 — GitHub REST API (whitelisted)
# =============================================================================
# Provides authenticated access to the GitHub API, restricted to the exact
# (method, path) pairs in _ALLOWED_ENDPOINTS.  The httpx.Client is
# instantiated once and reused across calls (connection pooling, keep-alive).
# =============================================================================


class GitHubAPIAction(Action):
    method: str = Field(description="HTTP method: GET, POST, PATCH, PUT, DELETE")
    endpoint: str = Field(
        description=(
            "GitHub API path (no base URL), e.g. "
            "/repos/OpenHands/OpenHands-CLI/issues or "
            "/search/issues"
        )
    )
    params: dict | None = Field(default=None, description="Query-string parameters")
    body: dict | None = Field(
        default=None, description="JSON request body for POST/PATCH/PUT"
    )


class GitHubAPIObservation(Observation):
    status_code: int = Field(description="HTTP response status code")
    data: dict | list | str | None = Field(default=None, description="Parsed JSON body")
    error: str | None = Field(default=None, description="Transport or decode error")

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        if self.error:
            return [TextContent(text=f"GitHub API error: {self.error}")]
        body = (
            json.dumps(self.data, indent=2)
            if not isinstance(self.data, str)
            else self.data
        )
        return [TextContent(text=f"HTTP {self.status_code}\n{body[:8000]}")]


# Explicit allowlist of (METHOD, compiled-regex) pairs the agent may call.
# [^/]+ matches exactly one path segment — it cannot cross a '/' boundary.
_ALLOWED_ENDPOINTS: list[tuple[str, re.Pattern[str]]] = [
    ("GET", re.compile(r"^/search/issues$")),
    ("GET", re.compile(r"^/repos/OpenHands/OpenHands-CLI/issues$")),
    ("GET", re.compile(r"^/repos/OpenHands/OpenHands-CLI/issues/[^/]+$")),
    ("GET", re.compile(r"^/repos/OpenHands/OpenHands-CLI/labels$")),
    ("POST", re.compile(r"^/repos/OpenHands/OpenHands-CLI/labels$")),
    ("POST", re.compile(r"^/repos/OpenHands/OpenHands-CLI/issues/[^/]+/labels$")),
]


def _is_allowed(method: str, endpoint: str) -> bool:
    return any(
        method.upper() == m and bool(p.fullmatch(endpoint))
        for m, p in _ALLOWED_ENDPOINTS
    )


class GitHubAPIExecutor(ToolExecutor[GitHubAPIAction, GitHubAPIObservation]):
    def __init__(self, token: str) -> None:
        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    def __call__(
        self,
        action: GitHubAPIAction,
        conversation=None,  # noqa: ARG002
    ) -> GitHubAPIObservation:
        if not _is_allowed(action.method, action.endpoint):
            return GitHubAPIObservation(
                status_code=403,
                error=(
                    f"{action.method.upper()} {action.endpoint} is not in the "
                    "allowed endpoint list."
                ),
            )
        try:
            resp = self._client.request(
                action.method.upper(),
                action.endpoint,
                params=action.params,
                json=action.body,
            )
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return GitHubAPIObservation(status_code=resp.status_code, data=data)
        except Exception as exc:
            return GitHubAPIObservation(status_code=0, error=str(exc))

    def close(self) -> None:
        self._client.close()


_GITHUB_API_DESCRIPTION = """\
Make authenticated GitHub REST API calls. The token is pre-configured.

Typical operations
------------------
Search recent open issues (last 7 days):
  method=GET
  endpoint=/search/issues
  params={"q": "repo:OpenHands/OpenHands-CLI is:issue is:open created:>=YYYY-MM-DD"}

Fetch a single issue:
  method=GET  endpoint=/repos/OpenHands/OpenHands-CLI/issues/{number}

List repo labels:
  method=GET  endpoint=/repos/OpenHands/OpenHands-CLI/labels

Create a label (if missing):
  method=POST  endpoint=/repos/OpenHands/OpenHands-CLI/labels
  body={"name": "good first issue", "color": "7057ff",
        "description": "Good first issue for new contributors"}

Apply labels to an issue:
  method=POST  endpoint=/repos/OpenHands/OpenHands-CLI/issues/{number}/labels
  body={"labels": ["good first issue"]}

Paginate with params={"page": 2, "per_page": 100} when needed.
"""


class GitHubAPITool(ToolDefinition[GitHubAPIAction, GitHubAPIObservation]):
    """Authenticated GitHub REST API — read + label operations."""

    @classmethod
    def create(cls, conv_state, **_) -> Sequence[ToolDefinition]:  # noqa: ARG003
        token = os.environ.get("GITHUB_TOKEN", "")
        return [
            cls(
                description=_GITHUB_API_DESCRIPTION,
                action_type=GitHubAPIAction,
                observation_type=GitHubAPIObservation,
                executor=GitHubAPIExecutor(token=token),
                annotations=ToolAnnotations(
                    readOnlyHint=False,  # can POST (create label / apply label)
                    destructiveHint=False,
                    idempotentHint=False,
                    openWorldHint=True,  # talks to external GitHub API
                ),
            )
        ]


register_tool(GitHubAPITool.name, GitHubAPITool)


# =============================================================================
# Tools 2 & 3 — Read-only working-directory file access
# =============================================================================
# GlobTool and PlanningFileEditorTool are imported above; importing them
# auto-registers them with the SDK tool registry.  No extra code needed.
# =============================================================================


# =============================================================================
# Main
# =============================================================================


def _load_prompt(repo_root: Path) -> str:
    prompt_path = repo_root / ".github" / "prompts" / "good-first-issue-labeler.md"
    if not prompt_path.exists():
        sys.exit(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Label qualifying GitHub issues as 'good first issue'.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--repo-root",
        default=str(_REPO_ROOT),
        metavar="DIR",
        help="Repository root directory (default: parent of .github/).",
    )
    args = parser.parse_args()

    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        sys.exit("Error: GITHUB_TOKEN environment variable is required.")

    llm_api_key = os.environ.get("LLM_API_KEY")
    if not llm_api_key:
        sys.exit("Error: LLM_API_KEY environment variable is required.")

    llm = LLM(
        model=os.environ.get("LLM_MODEL", "anthropic/claude-sonnet-4-5-20250929"),
        api_key=llm_api_key,
        base_url=os.environ.get("LLM_BASE_URL"),
    )

    tools = [
        Tool(name=GitHubAPITool.name),
        Tool(name=GlobTool.name),
        Tool(name=PlanningFileEditorTool.name),
    ]

    agent = Agent(llm=llm, tools=tools)

    repo_root = Path(args.repo_root).resolve()
    prompt = _load_prompt(repo_root)

    conversation = Conversation(agent=agent, workspace=str(repo_root))
    conversation.send_message(prompt)
    conversation.run()

    cost = llm.metrics.accumulated_cost
    print(f"\nDone. Accumulated LLM cost: ${cost:.4f}")


if __name__ == "__main__":
    main()
