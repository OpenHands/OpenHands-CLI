"""Cloud conversation creation functionality."""

import os
import subprocess
from typing import Any

from rich.console import Console

from openhands_cli.auth.api_client import OpenHandsApiClient
from openhands_cli.theme import OPENHANDS_THEME


console = Console()


class CloudConversationError(Exception):
    """Exception raised for cloud conversation errors."""


async def create_cloud_conversation(
    server_url: str, api_key: str, initial_user_msg: str
) -> dict[str, Any]:
    """Create a new conversation in OpenHands Cloud.

    Args:
        server_url: OpenHands server URL
        api_key: Valid API key for authentication
        initial_user_msg: Initial message for the conversation

    Returns:
        Conversation data from the server
    """

    client = OpenHandsApiClient(server_url, api_key)

    repo, branch = extract_repository_from_cwd()
    if repo:
        console.print(
            f"[{OPENHANDS_THEME.secondary}]Detected repository: "
            f"[{OPENHANDS_THEME.accent}]{repo}[/{OPENHANDS_THEME.accent}]"
            f"[/{OPENHANDS_THEME.secondary}]"
        )
    if branch:
        console.print(
            f"[{OPENHANDS_THEME.secondary}]Detected branch: "
            f"[{OPENHANDS_THEME.accent}]{branch}[/{OPENHANDS_THEME.accent}]"
            f"[/{OPENHANDS_THEME.secondary}]"
        )

    payload: dict[str, Any] = {"initial_user_msg": initial_user_msg}
    if repo:
        payload["repository"] = repo
    if branch:
        payload["selected_branch"] = branch

    console.print(
        f"[{OPENHANDS_THEME.accent}]"
        "Creating cloud conversation..."
        f"[/{OPENHANDS_THEME.accent}]"
    )

    try:
        resp = await client.create_conversation(json_data=payload)
        conversation = resp.json()
    except CloudConversationError:
        raise
    except Exception as e:
        console.print(
            f"[{OPENHANDS_THEME.error}]Error creating cloud conversation: {e}"
            f"[/{OPENHANDS_THEME.error}]"
        )
        raise CloudConversationError(f"Failed to create conversation: {e}") from e

    conversation_id = conversation.get("conversation_id")
    console.print(
        f"[{OPENHANDS_THEME.secondary}]Conversation ID: "
        f"[{OPENHANDS_THEME.accent}]{conversation_id}[/{OPENHANDS_THEME.accent}]"
        f"[/{OPENHANDS_THEME.secondary}]"
    )

    if conversation_id:
        url = f"{server_url}/conversations/{conversation_id}"
        console.print(
            f"[{OPENHANDS_THEME.secondary}]View in browser: "
            f"[{OPENHANDS_THEME.accent}]{url}[/{OPENHANDS_THEME.accent}]"
            f"[/{OPENHANDS_THEME.secondary}]"
        )

    return conversation


def _run_git(args: list[str]) -> str | None:
    try:
        res = subprocess.run(args, capture_output=True, text=True, check=True)
        out = res.stdout.strip()
        return out or None
    except Exception:
        return None


def _parse_repo_from_remote(remote_url: str) -> str | None:
    # SSH: git@github.com:owner/repo.git
    if remote_url.startswith("git@") and ":" in remote_url:
        return remote_url.split(":", 1)[1].removesuffix(".git") or None

    # HTTPS: https://github.com/owner/repo.git (or gitlab.com)
    if remote_url.startswith("https://"):
        parts = [p for p in remote_url.split("/") if p]
        if len(parts) >= 2:
            owner, repo = parts[-2], parts[-1].removesuffix(".git")
            if owner and repo:
                return f"{owner}/{repo}"
    return None


def extract_repository_from_cwd() -> tuple[str | None, str | None]:
    """Extract repository name (owner/repo) and current branch from CWD."""

    cwd = os.getcwd()
    remote = _run_git(["git", "-C", cwd, "remote", "get-url", "origin"])
    if not remote or ("github.com" not in remote and "gitlab.com" not in remote):
        return None, None

    repo = _parse_repo_from_remote(remote)
    if not repo:
        return None, None

    branch = _run_git(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"])
    return repo, branch
