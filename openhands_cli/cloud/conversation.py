"""Cloud conversation creation functionality."""

from typing import Any

from rich.console import Console

from openhands_cli.auth.api_client import OpenHandsApiClient, UnauthenticatedError
from openhands_cli.auth.logout_command import logout_command
from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.theme import OPENHANDS_THEME


console = Console()


class CloudConversationError(Exception):
    """Exception raised for cloud conversation errors."""


def _print_login_instructions(msg: str) -> None:
    console.print(f"[{OPENHANDS_THEME.error}]{msg}[/{OPENHANDS_THEME.error}]")
    console.print(
        f"[{OPENHANDS_THEME.secondary}]"
        "Please run the following command to authenticate:"
        f"[/{OPENHANDS_THEME.secondary}]"
    )
    console.print(
        f"[{OPENHANDS_THEME.accent}]  openhands login[/{OPENHANDS_THEME.accent}]"
    )


def _logout_and_instruct(server_url: str) -> None:
    console.print(
        f"[{OPENHANDS_THEME.warning}]Your connection with OpenHands Cloud has expired."
        f"[/{OPENHANDS_THEME.warning}]"
    )
    console.print(
        f"[{OPENHANDS_THEME.accent}]Logging you out...[/{OPENHANDS_THEME.accent}]"
    )
    logout_command(server_url)
    console.print(
        f"[{OPENHANDS_THEME.secondary}]"
        "Please re-run the following command "
        "to reconnect and retry:"
        f"[/{OPENHANDS_THEME.secondary}]"
    )
    console.print(
        f"[{OPENHANDS_THEME.accent}]  openhands login[/{OPENHANDS_THEME.accent}]"
    )


def require_api_key() -> str:
    """Return stored API key or raise with a helpful message."""
    store = TokenStorage()

    if not store.has_api_key():
        _print_login_instructions("Error: You are not logged in to OpenHands Cloud.")
        raise CloudConversationError("User not authenticated")

    api_key = store.get_api_key()
    if not api_key:
        _print_login_instructions("Error: Invalid API key stored.")
        raise CloudConversationError("Invalid API key")

    return api_key


async def is_token_valid(server_url: str, api_key: str) -> bool:
    """Validate token; return False for auth failures, raise for other errors."""
    client = OpenHandsApiClient(server_url, api_key)
    try:
        await client.get_user_info()
        return True
    except UnauthenticatedError:
        return False
    except Exception as e:
        raise CloudConversationError(f"Failed to validate token: {e}") from e


async def create_cloud_conversation(
    server_url: str, initial_user_msg: str
) -> dict[str, Any]:
    """Create a new conversation in OpenHands Cloud."""
    api_key = require_api_key()

    console.print(
        f"[{OPENHANDS_THEME.secondary}]Validating authentication..."
        f"[/{OPENHANDS_THEME.secondary}]"
    )
    if not await is_token_valid(server_url, api_key):
        _logout_and_instruct(server_url)
        raise CloudConversationError("Authentication expired - user logged out")

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
    import subprocess

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
    import os

    cwd = os.getcwd()
    remote = _run_git(["git", "-C", cwd, "remote", "get-url", "origin"])
    if not remote or ("github.com" not in remote and "gitlab.com" not in remote):
        return None, None

    repo = _parse_repo_from_remote(remote)
    if not repo:
        return None, None

    branch = _run_git(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"])
    return repo, branch
