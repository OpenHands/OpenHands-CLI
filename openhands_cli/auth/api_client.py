"""API client for fetching user data after OAuth authentication."""

import json
from typing import Any
from urllib.parse import urljoin

import httpx
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands.sdk import Agent
from openhands.sdk.context.condenser import LLMSummarizingCondenser
from openhands.sdk.llm import LLM
from openhands.tools.preset.default import get_default_tools
from openhands_cli.tui.settings.store import AgentStore


class ApiClientError(Exception):
    """Exception raised for API client errors."""

    pass


class OpenHandsApiClient:
    """Client for making authenticated API calls to OpenHands server."""

    def __init__(self, server_url: str, api_key: str):
        """Initialize the API client.

        Args:
            server_url: Base URL of the OpenHands server
            api_key: API key for authentication
        """
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.timeout = httpx.Timeout(30.0)

    async def get_llm_api_key(self) -> str | None:
        """Get the LLM API key for BYOR (Bring Your Own Runtime).

        Returns:
            The LLM API key if available, None otherwise

        Raises:
            ApiClientError: If the API call fails
        """
        url = urljoin(self.server_url, "/api/keys/llm/byor")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                result = response.json()
                return result.get("key")

        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                error_detail = error_data.get("detail", str(e))
            except (json.JSONDecodeError, AttributeError):
                error_detail = str(e)

            raise ApiClientError(f"Failed to get LLM API key: {error_detail}")

        except httpx.RequestError as e:
            raise ApiClientError(f"Network error getting LLM API key: {str(e)}")

    async def get_user_settings(self) -> dict[str, Any]:
        """Get the user's settings.

        Returns:
            Dictionary containing user settings

        Raises:
            ApiClientError: If the API call fails
        """
        url = urljoin(self.server_url, "/api/settings")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                return response.json()

        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                error_detail = error_data.get("detail", str(e))
            except (json.JSONDecodeError, AttributeError):
                error_detail = str(e)

            raise ApiClientError(f"Failed to get user settings: {error_detail}")

        except httpx.RequestError as e:
            raise ApiClientError(f"Network error getting user settings: {str(e)}")


async def fetch_user_data_after_oauth(server_url: str, api_key: str) -> dict[str, Any]:
    """Fetch user data after successful OAuth authentication.

    Args:
        server_url: OpenHands server URL
        api_key: API key obtained from OAuth

    Returns:
        Dictionary containing user data (llm_api_key, settings)

    Raises:
        ApiClientError: If any API call fails
    """
    client = OpenHandsApiClient(server_url, api_key)

    print_formatted_text(HTML("<cyan>Fetching user data...</cyan>"))

    user_data = {}

    try:
        # Fetch LLM API key
        print_formatted_text(HTML("<white>• Getting LLM API key...</white>"))
        llm_api_key = await client.get_llm_api_key()
        user_data["llm_api_key"] = llm_api_key

        if llm_api_key:
            print_formatted_text(
                HTML(f"<green>  ✓ LLM API key retrieved: {llm_api_key[:10]}...</green>")
            )
        else:
            print_formatted_text(HTML("<yellow>  ! No LLM API key available</yellow>"))

        # Fetch user settings
        print_formatted_text(HTML("<white>• Getting user settings...</white>"))
        settings = await client.get_user_settings()
        user_data["settings"] = settings

        # Display key settings information
        if settings:
            print_formatted_text(HTML("<green>  ✓ User settings retrieved</green>"))

            # Show some key settings
            llm_model = settings.get("llm_model", "Not set")
            agent = settings.get("agent", "Not set")
            language = settings.get("language", "Not set")

            print_formatted_text(HTML(f"    <white>LLM Model: {llm_model}</white>"))
            print_formatted_text(HTML(f"    <white>Agent: {agent}</white>"))
            print_formatted_text(HTML(f"    <white>Language: {language}</white>"))

            # Show if user has LLM API key set in settings
            llm_api_key_set = settings.get("llm_api_key_set", False)
            if llm_api_key_set:
                print_formatted_text(
                    HTML("    <green>✓ LLM API key is configured in settings</green>")
                )
            else:
                print_formatted_text(
                    HTML("    <yellow>! No LLM API key configured in settings</yellow>")
                )
        else:
            print_formatted_text(
                HTML("<yellow>  ! No user settings available</yellow>")
            )

        # Create and save Agent configuration if we have the necessary data
        if llm_api_key and settings:
            try:
                # Get the model from settings, default to reasonable model if not found
                model = settings.get("llm_model", "gpt-4o-mini")

                # Create LLM configuration for OpenHands provider
                llm = LLM(
                    model=model, api_key=llm_api_key, custom_llm_provider="openhands"
                )

                # Create LLM summarizing condenser with the same LLM
                condenser = LLMSummarizingCondenser(
                    llm=llm,
                    max_size=10000,  # Default max size
                    keep_first=1000,  # Keep first 1000 chars
                )

                # Create Agent with default tools
                agent = Agent(
                    llm=llm,
                    tools=get_default_tools(enable_browser=False),
                    mcp_config={},
                    condenser=condenser,
                )

                # Save the agent configuration
                agent_store = AgentStore()
                agent_store.save(agent)

                print_formatted_text(
                    HTML("<green>✓ Agent configuration created and saved!</green>")
                )

            except Exception as e:
                print_formatted_text(
                    HTML(
                        f"<yellow>Warning: Could not create agent configuration: "
                        f"{str(e)}</yellow>"
                    )
                )

        print_formatted_text(HTML("<green>✓ User data fetched successfully!</green>"))
        return user_data

    except ApiClientError as e:
        print_formatted_text(HTML(f"<red>Error fetching user data: {str(e)}</red>"))
        raise
