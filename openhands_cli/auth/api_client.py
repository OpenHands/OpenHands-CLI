"""API client for fetching user data after OAuth authentication."""

from typing import Any

from openhands.sdk.context.condenser import LLMSummarizingCondenser
from openhands_cli.auth.http_client import AuthHttpError, BaseHttpClient
from openhands_cli.auth.utils import _p
from openhands_cli.locations import AGENT_SETTINGS_PATH, PERSISTENCE_DIR
from openhands_cli.tui.settings.store import AgentStore


class ApiClientError(Exception):
    """Exception raised for API client errors."""

    pass


SETTINGS_PATH = f"{PERSISTENCE_DIR}/{AGENT_SETTINGS_PATH}"


class OpenHandsApiClient(BaseHttpClient):
    """Client for making authenticated API calls to OpenHands server."""

    def __init__(self, server_url: str, api_key: str):
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
            raise ApiClientError(f"Request to {path!r} failed: {e}") from e
        return response.json()

    async def get_llm_api_key(self) -> str | None:
        result = await self._get_json("/api/keys/llm/byor")
        return result.get("key")

    async def get_user_settings(self) -> dict[str, Any]:
        return await self._get_json("/api/settings")


def _print_settings_summary(settings: dict[str, Any]) -> None:
    _p("<green>  ✓ User settings retrieved</green>")

    llm_model = settings.get("llm_model", "Not set")
    agent_name = settings.get("agent", "Not set")
    language = settings.get("language", "Not set")
    llm_api_key_set = settings.get("llm_api_key_set", False)

    _p(f"    <white>LLM Model: {llm_model}</white>")
    _p(f"    <white>Agent: {agent_name}</white>")
    _p(f"    <white>Language: {language}</white>")

    if llm_api_key_set:
        _p("    <green>✓ LLM API key is configured in settings</green>")
    else:
        _p("    <yellow>! No LLM API key configured in settings</yellow>")


def create_and_save_agent_configuration(
    llm_api_key: str,
    settings: dict[str, Any],
) -> None:
    """Create and save an Agent configuration using AgentStore."""
    store = AgentStore()
    agent = store.create_and_save_from_settings(
        llm_api_key=llm_api_key,
        settings=settings,
    )

    _p("<green>✓ Agent configuration created and saved!</green>")
    _p("<white>Configuration details:</white>")

    llm = agent.llm

    _p(f"  • Model: <cyan>{llm.model}</cyan>")
    _p(f"  • Base URL: <cyan>{llm.base_url}</cyan>")
    _p(f"  • Usage ID: <cyan>{llm.usage_id}</cyan>")
    _p("  • API Key: <cyan>✓ Set</cyan>")

    tools_count = len(agent.tools)
    _p(f"  • Tools: <cyan>{tools_count} default tools loaded</cyan>")

    condenser = agent.condenser
    if isinstance(condenser, LLMSummarizingCondenser):
        _p(
            f"  • Condenser: <cyan>LLM Summarizing "
            f"(max_size: {condenser.max_size}, "
            f"keep_first: {condenser.keep_first})</cyan>"
        )

    _p(f"  • Saved to: <cyan>{SETTINGS_PATH}</cyan>")


async def fetch_user_data_after_oauth(
    server_url: str,
    api_key: str,
) -> dict[str, Any]:
    """Fetch user data after OAuth and optionally create & save an Agent."""
    client = OpenHandsApiClient(server_url, api_key)

    _p("<cyan>Fetching user data...</cyan>")

    try:
        # Fetch LLM API key
        _p("<white>• Getting LLM API key...</white>")
        llm_api_key = await client.get_llm_api_key()
        if llm_api_key:
            _p(f"<green>  ✓ LLM API key retrieved: {llm_api_key[:3]}...</green>")
        else:
            _p("<yellow>  ! No LLM API key available</yellow>")

        # Fetch user settings
        _p("<white>• Getting user settings...</white>")
        settings = await client.get_user_settings()

        if settings:
            _print_settings_summary(settings)
        else:
            _p("<yellow>  ! No user settings available</yellow>")

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
                _p(f"<yellow>{e}</yellow>")
                _p("<white>Keeping existing agent configuration.</white>")
            except Exception as e:
                _p(
                    f"<yellow>Warning: Could not create "
                    f"agent configuration: {e}</yellow>"
                )
        else:
            _p(
                "<yellow>Skipping agent configuration; "
                "missing key or settings.</yellow>"
            )

        _p("<green>✓ User data fetched successfully!</green>")
        return user_data

    except ApiClientError as e:
        _p(f"<red>Error fetching user data: {e}</red>")
        raise
