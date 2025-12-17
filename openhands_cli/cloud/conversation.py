"""Cloud conversation creation functionality."""

from typing import Any

from rich.console import Console

from openhands_cli.auth.api_client import OpenHandsApiClient
from openhands_cli.auth.token_storage import TokenStorage
from openhands_cli.theme import OPENHANDS_THEME


console = Console()


class CloudConversationError(Exception):
    """Exception raised for cloud conversation errors."""

    pass


def check_user_authentication(_server_url: str) -> str:
    """Check if user is authenticated and return API key.

    Args:
        server_url: The OpenHands server URL

    Returns:
        The API key if user is authenticated

    Raises:
        CloudConversationError: If user is not authenticated
    """
    token_storage = TokenStorage()

    if not token_storage.has_api_key():
        console.print(
            f"[{OPENHANDS_THEME.error}]Error: You are not logged in to "
            f"OpenHands Cloud.[/{OPENHANDS_THEME.error}]"
        )
        console.print(
            f"[{OPENHANDS_THEME.secondary}]Please run the following command "
            f"to authenticate:[/{OPENHANDS_THEME.secondary}]"
        )
        console.print(
            f"[{OPENHANDS_THEME.accent}]  openhands login[/{OPENHANDS_THEME.accent}]"
        )
        raise CloudConversationError("User not authenticated")

    api_key = token_storage.get_api_key()
    if not api_key:
        console.print(
            f"[{OPENHANDS_THEME.error}]Error: Invalid API key "
            f"stored.[/{OPENHANDS_THEME.error}]"
        )
        console.print(
            f"[{OPENHANDS_THEME.secondary}]Please run the following command "
            f"to re-authenticate:[/{OPENHANDS_THEME.secondary}]"
        )
        console.print(
            f"[{OPENHANDS_THEME.accent}]  openhands login[/{OPENHANDS_THEME.accent}]"
        )
        raise CloudConversationError("Invalid API key")

    return api_key


async def create_cloud_conversation(
    server_url: str,
    initial_user_msg: str,
) -> dict[str, Any]:
    """Create a new conversation in OpenHands Cloud.

    Args:
        server_url: The OpenHands server URL
        initial_user_msg: Initial message to seed the conversation

    Returns:
        The created conversation data

    Raises:
        CloudConversationError: If conversation creation fails
    """
    try:
        # Check authentication
        api_key = check_user_authentication(server_url)

        # Create API client
        client = OpenHandsApiClient(server_url, api_key)

        # Try to extract repository from current directory
        repository = None
        try:
            repository = extract_repository_from_cwd()
            if repository:
                console.print(
                    f"[{OPENHANDS_THEME.secondary}]Detected repository: "
                    f"[{OPENHANDS_THEME.accent}]{repository}"
                    f"[/{OPENHANDS_THEME.accent}][/{OPENHANDS_THEME.secondary}]"
                )
        except Exception as e:
            console.print(
                f"[{OPENHANDS_THEME.warning}]Warning: Could not detect "
                f"repository from current directory: {str(e)}"
                f"[/{OPENHANDS_THEME.warning}]"
            )

        # Prepare conversation data
        conversation_data = {
            "initial_user_msg": initial_user_msg,
        }

        if repository:
            conversation_data["repository"] = repository

        console.print(
            f"[{OPENHANDS_THEME.accent}]Creating cloud "
            f"conversation...[/{OPENHANDS_THEME.accent}]"
        )

        # Make API request to create conversation
        response = await client.post(
            "/api/conversations",
            json_data=conversation_data,
        )

        conversation = response.json()

        console.print(
            f"[{OPENHANDS_THEME.success}]✓ Cloud conversation created "
            f"successfully![/{OPENHANDS_THEME.success}]"
        )

        # Display conversation details
        conversation_id = conversation.get("id", "Unknown")
        conversation_url = conversation.get("url")

        console.print(
            f"[{OPENHANDS_THEME.secondary}]Conversation ID: "
            f"[{OPENHANDS_THEME.accent}]{conversation_id}"
            f"[/{OPENHANDS_THEME.accent}][/{OPENHANDS_THEME.secondary}]"
        )

        if conversation_url:
            console.print(
                f"[{OPENHANDS_THEME.secondary}]View in browser: "
                f"[{OPENHANDS_THEME.accent}]{conversation_url}"
                f"[/{OPENHANDS_THEME.accent}][/{OPENHANDS_THEME.secondary}]"
            )

        return conversation

    except Exception as e:
        if isinstance(e, CloudConversationError):
            raise

        console.print(
            f"[{OPENHANDS_THEME.error}]Error creating cloud conversation: "
            f"{str(e)}[/{OPENHANDS_THEME.error}]"
        )
        raise CloudConversationError(f"Failed to create conversation: {str(e)}")


def extract_repository_from_cwd() -> str | None:
    """Extract repository name from current working directory if it's a git repo.

    Returns:
        Repository name in format 'username/repo' or None if not a git repo
    """
    import os
    import subprocess

    try:
        # Check if we're in a git repository
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        if result.returncode != 0:
            return None

        remote_url = result.stdout.strip()

        # Parse GitHub/GitLab URLs
        if "github.com" in remote_url or "gitlab.com" in remote_url:
            # Handle both SSH and HTTPS URLs
            if remote_url.startswith("git@"):
                # SSH format: git@github.com:username/repo.git
                parts = remote_url.split(":")
                if len(parts) >= 2:
                    repo_part = parts[1].replace(".git", "")
                    return repo_part
            elif remote_url.startswith("https://"):
                # HTTPS format: https://github.com/username/repo.git
                parts = remote_url.split("/")
                if len(parts) >= 5:
                    username = parts[-2]
                    repo = parts[-1].replace(".git", "")
                    return f"{username}/{repo}"

        return None

    except (subprocess.SubprocessError, FileNotFoundError):
        return None
