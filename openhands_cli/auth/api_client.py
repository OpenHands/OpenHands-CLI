"""API client for fetching user data after OAuth authentication."""

from typing import Any

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands.sdk import Agent
from openhands.sdk.context.condenser import LLMSummarizingCondenser
from openhands.sdk.llm import LLM
from openhands.tools.preset.default import get_default_tools
from openhands_cli.auth.http_client import AuthHttpError, BaseHttpClient
from openhands_cli.tui.settings.store import AgentStore


class ApiClientError(Exception):
    """Exception raised for API client errors."""

    pass


class OpenHandsApiClient(BaseHttpClient):
    """Client for making authenticated API calls to OpenHands server."""

    def __init__(self, server_url: str, api_key: str):
        """Initialize the API client.

        Args:
            server_url: Base URL of the OpenHands server
            api_key: API key for authentication
        """
        super().__init__(server_url)
        self.api_key = api_key

    async def get_llm_api_key(self) -> str | None:
        """Get the LLM API key for BYOR (Bring Your Own Runtime).

        Returns:
            The LLM API key if available, None otherwise

        Raises:
            ApiClientError: If the API call fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await self.get("/api/keys/llm/byor", headers=headers)
            result = response.json()
            return result.get("key")

        except AuthHttpError as e:
            raise ApiClientError(f"Failed to get LLM API key: {str(e)}")

    async def get_user_settings(self) -> dict[str, Any]:
        """Get the user's settings.

        Returns:
            Dictionary containing user settings

        Raises:
            ApiClientError: If the API call fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await self.get("/api/settings", headers=headers)
            return response.json()

        except AuthHttpError as e:
            raise ApiClientError(f"Failed to get user settings: {str(e)}")


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

                # Create LLM configuration for agent
                llm = LLM(
                    model=model,
                    api_key=llm_api_key,
                    base_url="https://llm-proxy.app.all-hands.dev/",
                    usage_id="agent",
                )

                # Create separate LLM for condenser to ensure different usage tracking
                condenser_llm = LLM(
                    model=model,
                    api_key=llm_api_key,
                    base_url="https://llm-proxy.app.all-hands.dev/",
                    usage_id="condenser",
                )

                # Create LLM summarizing condenser with separate LLM
                condenser = LLMSummarizingCondenser(
                    llm=condenser_llm,
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

                # Log what was saved (without exposing the API key)
                print_formatted_text(HTML("<white>Configuration details:</white>"))
                print_formatted_text(HTML(f"  • Model: <cyan>{model}</cyan>"))
                print_formatted_text(HTML(f"  • Base URL: <cyan>{llm.base_url}</cyan>"))
                print_formatted_text(HTML(f"  • Usage ID: <cyan>{llm.usage_id}</cyan>"))
                api_key_status = "✓ Set" if llm_api_key else "✗ Not set"
                print_formatted_text(
                    HTML(f"  • API Key: <cyan>{api_key_status}</cyan>")
                )
                tools_count = len(agent.tools)
                print_formatted_text(
                    HTML(f"  • Tools: <cyan>{tools_count} default tools loaded</cyan>")
                )
                condenser_info = (
                    f"LLM Summarizing (max_size: {condenser.max_size}, "
                    f"keep_first: {condenser.keep_first})"
                )
                print_formatted_text(
                    HTML(f"  • Condenser: <cyan>{condenser_info}</cyan>")
                )

                # Show where settings were saved
                from openhands_cli.locations import AGENT_SETTINGS_PATH, PERSISTENCE_DIR

                settings_path = f"{PERSISTENCE_DIR}/{AGENT_SETTINGS_PATH}"
                print_formatted_text(
                    HTML(f"  • Saved to: <cyan>{settings_path}</cyan>")
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
