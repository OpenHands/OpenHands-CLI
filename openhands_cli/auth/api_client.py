"""API client for fetching user data after OAuth authentication."""

import html
from typing import Any

import httpx

from openhands.sdk import Agent
from openhands.sdk.context.condenser import LLMSummarizingCondenser
from openhands_cli.auth.http_client import AuthHttpError, BaseHttpClient
from openhands_cli.auth.utils import console_print
from openhands_cli.locations import AGENT_SETTINGS_PATH, get_persistence_dir
from openhands_cli.stores import AgentStore
from openhands_cli.theme import OPENHANDS_THEME


class ApiClientError(Exception):
    """Exception raised for API client errors."""

    pass


class UnauthenticatedError(ApiClientError):
    """Exception raised when user is not authenticated (401 response)."""

    pass


def get_settings_path() -> str:
    """Get the full path to the agent settings file."""
    return f"{get_persistence_dir()}/{AGENT_SETTINGS_PATH}"


class OpenHandsApiClient(BaseHttpClient):
    """Client for making authenticated API calls to OpenHands server."""

    def __init__(self, server_url: str, api_key: str) -> None:
        super().__init__(server_url)
        self.api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _get_json(self, path: str) -> dict[str, Any]:
        """Perform GET and return JSON with unified error handling."""
        try:
            response = await self.get(path, headers=self._headers)
        except AuthHttpError as e:
            # Check if this is a 401 Unauthorized error
            if "HTTP 401" in str(e):
                raise UnauthenticatedError(
                    f"Authentication failed for {path!r}: {e}"
                ) from e
            raise ApiClientError(f"Request to {path!r} failed: {e}") from e
        return response.json()

    async def get_user_info(self) -> dict[str, Any]:
        """Get user information from the API.

        Returns:
            User information dictionary

        Raises:
            UnauthenticatedError: If the user is not authenticated (401 response)
            ApiClientError: For other API errors
        """
        return await self._get_json("/api/user/info")

    async def get_llm_api_key(self) -> str | None:
        result = await self._get_json("/api/keys/llm/byor")
        return result.get("key")

    async def get_user_settings(self) -> dict[str, Any]:
        return await self._get_json("/api/settings")

    async def create_conversation(
        self, json_data: dict[str, Any] | None = None
    ) -> httpx.Response:
        return await self.post("/api/conversations", self._headers, json_data)

    async def get_conversation_info(
        self, conversation_id: str
    ) -> dict[str, Any] | None:
        """Get conversation information including sandbox_id.

        Args:
            conversation_id: The conversation ID to look up

        Returns:
            Conversation info dict if found, None if not found

        Raises:
            UnauthenticatedError: If the user is not authenticated (401 response)
            ApiClientError: For other API errors
        """
        path = f"/api/v1/app-conversations?ids={conversation_id}"
        try:
            response = await self.get(path, headers=self._headers)
        except AuthHttpError as e:
            if "HTTP 401" in str(e):
                raise UnauthenticatedError(
                    f"Authentication failed for {path!r}: {e}"
                ) from e
            raise ApiClientError(f"Request to {path!r} failed: {e}") from e

        data: list[dict[str, Any]] = response.json()
        if len(data) > 0:
            return data[0]
        return None


def _print_settings_summary(settings: dict[str, Any]) -> None:
    console_print(
        f"[{OPENHANDS_THEME.success}]  ✓ User "
        f"settings retrieved[/{OPENHANDS_THEME.success}]"
    )

    llm_model = settings.get("llm_model", "Not set")
    agent_name = settings.get("agent", "Not set")
    language = settings.get("language", "Not set")
    llm_api_key_set = settings.get("llm_api_key_set", False)

    console_print(
        f"    [{OPENHANDS_THEME.secondary}]LLM Model: "
        f"{llm_model}[/{OPENHANDS_THEME.secondary}]"
    )
    console_print(
        f"    [{OPENHANDS_THEME.secondary}]Agent: "
        f"{agent_name}[/{OPENHANDS_THEME.secondary}]"
    )
    console_print(
        f"    [{OPENHANDS_THEME.secondary}]Language: "
        f"{language}[/{OPENHANDS_THEME.secondary}]"
    )

    if llm_api_key_set:
        console_print(
            f"    [{OPENHANDS_THEME.success}]✓ LLM API key is configured in "
            f"settings[/{OPENHANDS_THEME.success}]"
        )
    else:
        console_print(
            f"    [{OPENHANDS_THEME.warning}]! No LLM API key configured in "
            f"settings[/{OPENHANDS_THEME.warning}]"
        )


def _ask_user_consent_for_overwrite(
    existing_agent: Agent,
    new_settings: dict[str, str],
    default_model: str = "claude-sonnet-4-5-20250929",
) -> bool:
    """Ask user for consent to overwrite existing agent configuration.

    Args:
        existing_agent: The existing agent configuration
        new_settings: New settings from cloud
        base_url: Base URL for the new configuration
        default_model: Default model if not specified in settings

    Returns:
        True if user consents to overwrite, False otherwise
    """
    console_print(
        f"\n[{OPENHANDS_THEME.warning}]⚠️  Existing agent configuration found!"
        f"[/{OPENHANDS_THEME.warning}]"
    )
    console_print(
        f"[{OPENHANDS_THEME.secondary}]This will overwrite your current settings with "
        f"the ones from OpenHands Cloud.[/{OPENHANDS_THEME.secondary}]\n"
    )

    # Show current vs new settings comparison
    current_model = existing_agent.llm.model
    new_model = new_settings.get("llm_model", default_model)
    base_url = new_settings.get("llm_base_url", None)

    console_print(
        f"[{OPENHANDS_THEME.secondary}]Current "
        f"configuration:[/{OPENHANDS_THEME.secondary}]"
    )
    console_print(
        f"  • Model: [{OPENHANDS_THEME.accent}]{html.escape(current_model)}"
        f"[/{OPENHANDS_THEME.accent}]"
    )

    if existing_agent.llm.base_url:
        console_print(
            f"  • Base URL: [{OPENHANDS_THEME.accent}]"
            f"{html.escape(existing_agent.llm.base_url)}[/{OPENHANDS_THEME.accent}]"
        )

    console_print(
        f"\n[{OPENHANDS_THEME.secondary}]New configuration from "
        f"cloud:[/{OPENHANDS_THEME.secondary}]"
    )
    console_print(
        f"  • Model: [{OPENHANDS_THEME.accent}]{html.escape(new_model)}"
        f"[/{OPENHANDS_THEME.accent}]"
    )

    if base_url:
        console_print(
            f"  • Base URL: [{OPENHANDS_THEME.accent}]{html.escape(base_url)}"
            f"[/{OPENHANDS_THEME.accent}]"
        )

    try:
        response = (
            input("\nDo you want to overwrite your existing configuration?(y/N): ")
            .lower()
            .strip()
        )
        print("\n")

        return response in ("y", "yes")

    except (KeyboardInterrupt, EOFError):
        return False


def create_and_save_agent_configuration(
    llm_api_key: str,
    settings: dict[str, Any],
) -> None:
    """Create and save an Agent configuration using AgentStore.

    This function handles the consent logic by:
    1. Loading existing agent configuration
    2. If exists, asking user for consent to overwrite
    3. Only proceeding if user consents or no existing config
    """
    store = AgentStore()

    # First, check if existing configuration exists on disk
    existing_agent = store.load_from_disk()
    if existing_agent is not None:
        # Ask for user consent
        if not _ask_user_consent_for_overwrite(
            existing_agent,
            settings,
        ):
            raise ValueError("User declined to overwrite existing configuration")

    # User consented or no existing config - proceed with creation
    agent = store.create_and_save_from_settings(
        llm_api_key=llm_api_key,
        settings=settings,
    )

    console_print(
        f"[{OPENHANDS_THEME.success}]✓ Agent configuration created and "
        f"saved![/{OPENHANDS_THEME.success}]"
    )
    console_print(
        f"[{OPENHANDS_THEME.secondary}]Configuration "
        f"details:[/{OPENHANDS_THEME.secondary}]"
    )

    llm = agent.llm

    console_print(
        f"  • Model: [{OPENHANDS_THEME.accent}]{llm.model}[/{OPENHANDS_THEME.accent}]"
    )
    console_print(
        f"  • Base URL: [{OPENHANDS_THEME.accent}]{llm.base_url}"
        f"[/{OPENHANDS_THEME.accent}]"
    )
    console_print(
        f"  • Usage ID: [{OPENHANDS_THEME.accent}]{llm.usage_id}"
        f"[/{OPENHANDS_THEME.accent}]"
    )
    console_print(
        f"  • API Key: [{OPENHANDS_THEME.accent}]✓ Set[/{OPENHANDS_THEME.accent}]"
    )

    tools_count = len(agent.tools)
    console_print(
        f"  • Tools: [{OPENHANDS_THEME.accent}]{tools_count} default tools loaded"
        f"[/{OPENHANDS_THEME.accent}]"
    )

    condenser = agent.condenser
    if isinstance(condenser, LLMSummarizingCondenser):
        console_print(
            f"  • Condenser: [{OPENHANDS_THEME.accent}]LLM Summarizing "
            f"(max_size: {condenser.max_size}, "
            f"keep_first: {condenser.keep_first})[/{OPENHANDS_THEME.accent}]"
        )

    console_print(
        f"  • Saved to: [{OPENHANDS_THEME.accent}]{get_settings_path()}"
        f"[/{OPENHANDS_THEME.accent}]"
    )


async def fetch_user_data_after_oauth(
    server_url: str,
    api_key: str,
) -> dict[str, Any]:
    """Fetch user data after OAuth and optionally create & save an Agent."""
    client = OpenHandsApiClient(server_url, api_key)

    console_print(
        f"[{OPENHANDS_THEME.accent}]Fetching user data...[/{OPENHANDS_THEME.accent}]"
    )

    try:
        # Fetch LLM API key
        console_print(
            f"[{OPENHANDS_THEME.secondary}]• Getting LLM API key..."
            f"[/{OPENHANDS_THEME.secondary}]"
        )
        llm_api_key = await client.get_llm_api_key()
        if llm_api_key:
            console_print(
                f"[{OPENHANDS_THEME.success}]  ✓ LLM API key retrieved: "
                f"{llm_api_key[:3]}...[/{OPENHANDS_THEME.success}]"
            )
        else:
            console_print(
                f"[{OPENHANDS_THEME.warning}]  ! No "
                f"LLM API key available[/{OPENHANDS_THEME.warning}]"
            )

        # Fetch user settings
        console_print(
            f"[{OPENHANDS_THEME.secondary}]• Getting user settings..."
            f"[/{OPENHANDS_THEME.secondary}]"
        )
        settings = await client.get_user_settings()

        if settings:
            _print_settings_summary(settings)
        else:
            console_print(
                f"[{OPENHANDS_THEME.warning}]  ! No "
                f"user settings available[/{OPENHANDS_THEME.warning}]"
            )

        user_data = {
            "llm_api_key": llm_api_key,
            "settings": settings,
        }

        # Create agent if possible
        if llm_api_key and settings:
            try:
                create_and_save_agent_configuration(llm_api_key, settings)
            except ValueError as e:
                # User declined to overwrite existing configuration
                console_print("\n")
                console_print(
                    f"[{OPENHANDS_THEME.warning}]{e}[/{OPENHANDS_THEME.warning}]"
                )
                console_print(
                    f"[{OPENHANDS_THEME.secondary}]Keeping existing "
                    f"agent configuration.[/{OPENHANDS_THEME.secondary}]"
                )
            except Exception as e:
                console_print(
                    f"[{OPENHANDS_THEME.warning}]Warning: Could not create "
                    f"agent configuration: {e}[/{OPENHANDS_THEME.warning}]"
                )
        else:
            console_print(
                f"[{OPENHANDS_THEME.warning}]Skipping agent configuration; "
                f"missing key or settings.[/{OPENHANDS_THEME.warning}]"
            )

        console_print(
            f"[{OPENHANDS_THEME.success}]✓ User data "
            f"fetched successfully![/{OPENHANDS_THEME.success}]"
        )
        return user_data

    except ApiClientError as e:
        console_print(
            f"[{OPENHANDS_THEME.error}]Error fetching user data: "
            f"{e}[/{OPENHANDS_THEME.error}]"
        )
        raise
