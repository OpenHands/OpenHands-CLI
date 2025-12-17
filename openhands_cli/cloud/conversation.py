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


async def validate_token(server_url: str, api_key: str) -> bool:
    """Validate the API token by making a test request.

    Args:
        server_url: The OpenHands server URL
        api_key: The API key to validate

    Returns:
        True if token is valid, False if invalid

    Raises:
        CloudConversationError: For non-authentication related errors
    """
    try:
        client = OpenHandsApiClient(server_url, api_key)
        await client.get_user_info()
        return True
    except UnauthenticatedError:
        return False
    except Exception as e:
        # For other errors, we still raise them as they might be network issues, etc.
        raise CloudConversationError(f"Failed to validate token: {str(e)}")


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

        # Validate the token before proceeding
        console.print(
            f"[{OPENHANDS_THEME.secondary}]Validating authentication..."
            f"[/{OPENHANDS_THEME.secondary}]"
        )

        is_valid = await validate_token(server_url, api_key)
        if not is_valid:
            # Token is invalid, log out the user
            console.print(
                f"[{OPENHANDS_THEME.warning}]Your connection with OpenHands Cloud "
                f"has expired.[/{OPENHANDS_THEME.warning}]"
            )
            console.print(
                f"[{OPENHANDS_THEME.accent}]Logging you out..."
                f"[/{OPENHANDS_THEME.accent}]"
            )

            logout_command(server_url)

            console.print(
                f"[{OPENHANDS_THEME.secondary}]Please re-run the following command "
                f"to reconnect and retry:[/{OPENHANDS_THEME.secondary}]"
            )
            console.print(
                f"[{OPENHANDS_THEME.accent}]  openhands login"
                f"[/{OPENHANDS_THEME.accent}]"
            )
            raise CloudConversationError("Authentication expired - user logged out")

        # Create API client
        client = OpenHandsApiClient(server_url, api_key)

        # Try to extract repository and branch from current directory
        repository = None
        selected_branch = None
        try:
            repository, selected_branch = extract_repository_from_cwd()
            if repository:
                console.print(
                    f"[{OPENHANDS_THEME.secondary}]Detected repository: "
                    f"[{OPENHANDS_THEME.accent}]{repository}"
                    f"[/{OPENHANDS_THEME.accent}][/{OPENHANDS_THEME.secondary}]"
                )
                if selected_branch:
                    console.print(
                        f"[{OPENHANDS_THEME.secondary}]Detected branch: "
                        f"[{OPENHANDS_THEME.accent}]{selected_branch}"
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

        if selected_branch:
            conversation_data["selected_branch"] = selected_branch

        console.print(
            f"[{OPENHANDS_THEME.accent}]Creating cloud "
            f"conversation...[/{OPENHANDS_THEME.accent}]"
        )

        # Make API request to create conversation
        response = await client.create_conversation(
            json_data=conversation_data,
        )

        conversation = response.json()

        # Display conversation details
        conversation_id = conversation.get("conversation_id")
        conversation_url = (
            server_url + f"/conversations/{conversation_id}"
            if conversation_id
            else None
        )

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


def extract_repository_from_cwd() -> tuple[str | None, str | None]:
    """Extract repository name and current branch from current working directory.

    Returns:
        Tuple of (repository_name, branch_name) where:
        - repository_name: Repository name in format 'username/repo' or None
        - branch_name: Current branch name or None if detection fails
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
            return None, None

        remote_url = result.stdout.strip()
        repository = None

        # Parse GitHub/GitLab URLs
        if "github.com" in remote_url or "gitlab.com" in remote_url:
            # Handle both SSH and HTTPS URLs
            if remote_url.startswith("git@"):
                # SSH format: git@github.com:username/repo.git
                parts = remote_url.split(":")
                if len(parts) >= 2:
                    repo_part = parts[1].replace(".git", "")
                    repository = repo_part
            elif remote_url.startswith("https://"):
                # HTTPS format: https://github.com/username/repo.git
                parts = remote_url.split("/")
                if len(parts) >= 5:
                    username = parts[-2]
                    repo = parts[-1].replace(".git", "")
                    repository = f"{username}/{repo}"

        # Get current branch name
        branch = None
        if repository:  # Only get branch if we have a valid repository
            try:
                branch_result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True,
                    text=True,
                    cwd=os.getcwd(),
                )
                if branch_result.returncode == 0:
                    branch = branch_result.stdout.strip()
            except (subprocess.SubprocessError, FileNotFoundError):
                # Branch detection failed, but we still have repository info
                pass

        return repository, branch

    except (subprocess.SubprocessError, FileNotFoundError):
        return None, None
