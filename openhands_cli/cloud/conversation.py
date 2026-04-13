"""Cloud conversation creation functionality.

ARCHITECTURAL NOTE:
This module contains direct API implementation for conversation management.
This logic is slated for migration to `openhands_cli/conversations/store/cloud.py`.

The goal is to have a unified `ConversationStore` interface where:
- `LocalFileStore` handles local filesystem operations.
- `CloudStore` handles these API interactions.

Future maintainers: Please move methods from here into the `CloudStore` class
implementation and deprecate this module.
"""

import asyncio
import logging
import os
import subprocess
from typing import Any

from openhands_cli.auth.api_client import OpenHandsApiClient
from openhands_cli.auth.utils import console_print
from openhands_cli.theme import OPENHANDS_THEME


logger = logging.getLogger(__name__)


class CloudConversationError(Exception):
    """Exception raised for cloud conversation errors."""


async def create_cloud_conversation(
    server_url: str,
    api_key: str,
    initial_user_msg: str,
    *,
    poll_interval: float = 2.0,
    poll_max_attempts: int = 15,
) -> dict[str, Any]:
    """Create a new conversation in OpenHands Cloud.

    Args:
        server_url: OpenHands server URL
        api_key: Valid API key for authentication
        initial_user_msg: Initial message for the conversation
        poll_interval: Seconds between start-task polling attempts
        poll_max_attempts: Maximum number of polling attempts

    Returns:
        Conversation data from the server
    """

    client = OpenHandsApiClient(server_url, api_key)

    repo, branch = extract_repository_from_cwd()
    accent = OPENHANDS_THEME.accent
    if repo:
        console_print(
            f"Detected repository: [{accent}]{repo}[/{accent}]",
            style=OPENHANDS_THEME.secondary,
        )
    if branch:
        console_print(
            f"Detected branch: [{accent}]{branch}[/{accent}]",
            style=OPENHANDS_THEME.secondary,
        )

    payload: dict[str, Any] = {
        "initial_message": {
            "content": [{"type": "text", "text": initial_user_msg}],
        }
    }
    if repo:
        payload["selected_repository"] = repo
    if branch:
        payload["selected_branch"] = branch

    console_print("Creating cloud conversation...", style=OPENHANDS_THEME.accent)

    try:
        resp = await client.create_conversation(json_data=payload)
        conversation = resp.json()
    except CloudConversationError:
        raise
    except Exception as e:
        console_print(
            f"Error creating cloud conversation: {e}", style=OPENHANDS_THEME.error
        )
        raise CloudConversationError(f"Failed to create conversation: {e}") from e

    task_id = conversation.get("id")
    app_conversation_id = conversation.get("app_conversation_id")

    # V1 returns a start-task; poll until app_conversation_id is available
    if not app_conversation_id and task_id:
        console_print(
            "Waiting for conversation to start...", style=OPENHANDS_THEME.secondary
        )
        for _ in range(poll_max_attempts):
            await asyncio.sleep(poll_interval)
            task_info = await client.get_start_task_status(task_id)
            if task_info:
                status = task_info.get("status")
                app_conversation_id = task_info.get("app_conversation_id")
                if app_conversation_id:
                    break
                if status == "ERROR":
                    detail = task_info.get("detail", "Unknown error")
                    raise CloudConversationError(
                        f"Conversation failed to start: {detail}"
                    )

    conversation_id = app_conversation_id or task_id
    if not app_conversation_id:
        console_print(
            "⚠️ Conversation is still initializing. "
            "The link below may take a moment to become active.",
            style=OPENHANDS_THEME.warning,
        )
    console_print(
        f"Conversation ID: [{accent}]{conversation_id}[/{accent}]",
        style=OPENHANDS_THEME.secondary,
    )

    if conversation_id:
        url = f"{server_url}/conversations/{conversation_id}"
        console_print(
            f"View in browser: [{accent}]{url}[/{accent}]",
            style=OPENHANDS_THEME.secondary,
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
