"""Unit tests for API client functionality."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from openhands_cli.auth.api_client import (
    ApiClientError,
    OpenHandsApiClient,
    create_agent_from_settings,
    fetch_user_data_after_oauth,
    save_agent_configuration,
)


class TestOpenHandsApiClient:
    """Test cases for OpenHandsApiClient class."""

    def test_init(self):
        """Test OpenHandsApiClient initialization."""
        server_url = "https://api.example.com"
        api_key = "test-api-key"

        client = OpenHandsApiClient(server_url, api_key)

        assert client.server_url == server_url
        assert client.api_key == api_key
        assert client._headers == {
            "Authorization": "Bearer test-api-key",
            "Content-Type": "application/json",
        }

    @pytest.mark.asyncio
    async def test_get_json_success(self):
        """Test successful JSON GET request."""
        client = OpenHandsApiClient("https://api.example.com", "test-key")

        mock_response = httpx.Response(status_code=200)
        mock_response._content = json.dumps({"key": "value"}).encode()

        with patch.object(client, "get") as mock_get:
            mock_get.return_value = mock_response

            result = await client._get_json("/test")

            assert result == {"key": "value"}
            mock_get.assert_called_once_with("/test", headers=client._headers)

    @pytest.mark.asyncio
    async def test_get_json_http_error(self):
        """Test JSON GET request with HTTP error."""
        client = OpenHandsApiClient("https://api.example.com", "test-key")

        with patch.object(client, "get") as mock_get:
            from openhands_cli.auth.http_client import AuthHttpError

            mock_get.side_effect = AuthHttpError("Network error")

            with pytest.raises(
                ApiClientError, match="Request to '/test' failed: Network error"
            ):
                await client._get_json("/test")

    @pytest.mark.asyncio
    async def test_get_llm_api_key_success(self):
        """Test successful LLM API key retrieval."""
        client = OpenHandsApiClient("https://api.example.com", "test-key")

        with patch.object(client, "_get_json") as mock_get_json:
            mock_get_json.return_value = {"key": "llm-api-key-123"}

            result = await client.get_llm_api_key()

            assert result == "llm-api-key-123"
            mock_get_json.assert_called_once_with("/api/keys/llm/byor")

    @pytest.mark.asyncio
    async def test_get_llm_api_key_no_key(self):
        """Test LLM API key retrieval when no key is present."""
        client = OpenHandsApiClient("https://api.example.com", "test-key")

        with patch.object(client, "_get_json") as mock_get_json:
            mock_get_json.return_value = {}

            result = await client.get_llm_api_key()

            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_settings_success(self):
        """Test successful user settings retrieval."""
        client = OpenHandsApiClient("https://api.example.com", "test-key")

        expected_settings = {
            "llm_model": "gpt-4o-mini",
            "agent": "CodeActAgent",
            "language": "en",
        }

        with patch.object(client, "_get_json") as mock_get_json:
            mock_get_json.return_value = expected_settings

            result = await client.get_user_settings()

            assert result == expected_settings
            mock_get_json.assert_called_once_with("/api/settings")


class TestHelperFunctions:
    """Test cases for helper functions in api_client module."""

    def test_create_agent_from_settings(self):
        """Test agent creation from settings."""
        llm_api_key = "test-llm-key"
        settings = {"llm_model": "gpt-4o", "agent": "CodeActAgent", "language": "en"}

        with patch("openhands_cli.auth.api_client.LLM") as mock_llm_class:
            with patch(
                "openhands_cli.auth.api_client.LLMSummarizingCondenser"
            ) as mock_condenser_class:
                with patch("openhands_cli.auth.api_client.Agent") as mock_agent_class:
                    with patch(
                        "openhands_cli.auth.api_client.get_default_tools"
                    ) as mock_get_tools:
                        mock_llm = MagicMock()
                        mock_llm_class.return_value = mock_llm

                        mock_condenser = MagicMock()
                        mock_condenser_class.return_value = mock_condenser

                        mock_agent = MagicMock()
                        mock_agent_class.return_value = mock_agent

                        mock_tools = [MagicMock()]
                        mock_get_tools.return_value = mock_tools

                        result = create_agent_from_settings(llm_api_key, settings)

                        assert result == mock_agent

                        # Verify LLM creation (called twice - main and condenser)
                        assert mock_llm_class.call_count == 2

                        # Verify agent creation
                        mock_agent_class.assert_called_once_with(
                            llm=mock_llm,
                            tools=mock_tools,
                            mcp_config={},
                            condenser=mock_condenser,
                        )

    def test_create_agent_from_settings_default_model(self):
        """Test agent creation with default model when not specified."""
        llm_api_key = "test-llm-key"
        settings = {}  # No model specified

        with patch("openhands_cli.auth.api_client.LLM") as mock_llm_class:
            with patch("openhands_cli.auth.api_client.LLMSummarizingCondenser"):
                with patch("openhands_cli.auth.api_client.Agent"):
                    with patch("openhands_cli.auth.api_client.get_default_tools"):
                        create_agent_from_settings(llm_api_key, settings)

                        # Should use default model
                        mock_llm_class.assert_any_call(
                            model="gpt-4o-mini",
                            api_key=llm_api_key,
                            base_url="https://llm-proxy.app.all-hands.dev/",
                            usage_id="agent",
                        )

    def test_save_agent_configuration(self):
        """Test saving agent configuration."""
        mock_agent = MagicMock()
        mock_llm = MagicMock()
        mock_llm.model = "gpt-4o"
        mock_llm.base_url = "https://api.openai.com"
        mock_llm.usage_id = "test-agent"
        mock_agent.llm = mock_llm
        mock_agent.tools = [MagicMock(), MagicMock()]

        mock_condenser = MagicMock()
        mock_condenser.max_size = 10000
        mock_condenser.keep_first = 1000
        mock_agent.condenser = mock_condenser

        with patch("openhands_cli.auth.api_client.AgentStore") as mock_store_class:
            with patch("openhands_cli.auth.api_client._p") as mock_print:
                mock_store = MagicMock()
                mock_store_class.return_value = mock_store

                save_agent_configuration(mock_agent)

                mock_store.save.assert_called_once_with(mock_agent)
                assert mock_print.call_count >= 5  # Multiple print statements

    @pytest.mark.asyncio
    async def test_fetch_user_data_after_oauth_success(self):
        """Test successful user data fetching after OAuth."""
        server_url = "https://api.example.com"
        api_key = "test-api-key"

        with patch(
            "openhands_cli.auth.api_client.OpenHandsApiClient"
        ) as mock_client_class:
            with patch(
                "openhands_cli.auth.api_client.create_agent_from_settings"
            ) as mock_create_agent:
                with patch(
                    "openhands_cli.auth.api_client.save_agent_configuration"
                ) as mock_save_agent:
                    with patch("openhands_cli.auth.api_client._p"):
                        mock_client = AsyncMock()
                        mock_client_class.return_value = mock_client

                        mock_client.get_llm_api_key.return_value = "llm-key-123"
                        mock_client.get_user_settings.return_value = {
                            "llm_model": "gpt-4o",
                            "agent": "CodeActAgent",
                        }

                        mock_agent = MagicMock()
                        mock_create_agent.return_value = mock_agent

                        result = await fetch_user_data_after_oauth(server_url, api_key)

                        expected_result = {
                            "llm_api_key": "llm-key-123",
                            "settings": {
                                "llm_model": "gpt-4o",
                                "agent": "CodeActAgent",
                            },
                        }
                        assert result == expected_result

                        mock_client.get_llm_api_key.assert_called_once()
                        mock_client.get_user_settings.assert_called_once()
                        mock_create_agent.assert_called_once()
                        mock_save_agent.assert_called_once_with(mock_agent)

    @pytest.mark.asyncio
    async def test_fetch_user_data_after_oauth_no_llm_key(self):
        """Test user data fetching when no LLM API key is available."""
        server_url = "https://api.example.com"
        api_key = "test-api-key"

        with patch(
            "openhands_cli.auth.api_client.OpenHandsApiClient"
        ) as mock_client_class:
            with patch("openhands_cli.auth.api_client._p"):
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                mock_client.get_llm_api_key.return_value = None
                mock_client.get_user_settings.return_value = {"agent": "CodeActAgent"}

                result = await fetch_user_data_after_oauth(server_url, api_key)

                expected_result = {
                    "llm_api_key": None,
                    "settings": {"agent": "CodeActAgent"},
                }
                assert result == expected_result

    @pytest.mark.asyncio
    async def test_fetch_user_data_after_oauth_no_settings(self):
        """Test user data fetching when no settings are available."""
        server_url = "https://api.example.com"
        api_key = "test-api-key"

        with patch(
            "openhands_cli.auth.api_client.OpenHandsApiClient"
        ) as mock_client_class:
            with patch("openhands_cli.auth.api_client._p"):
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                mock_client.get_llm_api_key.return_value = "llm-key-123"
                mock_client.get_user_settings.return_value = None

                result = await fetch_user_data_after_oauth(server_url, api_key)

                expected_result = {"llm_api_key": "llm-key-123", "settings": None}
                assert result == expected_result

    @pytest.mark.asyncio
    async def test_fetch_user_data_after_oauth_agent_creation_error(self):
        """Test user data fetching when agent creation fails."""
        server_url = "https://api.example.com"
        api_key = "test-api-key"

        with patch(
            "openhands_cli.auth.api_client.OpenHandsApiClient"
        ) as mock_client_class:
            with patch(
                "openhands_cli.auth.api_client.create_agent_from_settings"
            ) as mock_create_agent:
                with patch("openhands_cli.auth.api_client._p"):
                    mock_client = AsyncMock()
                    mock_client_class.return_value = mock_client

                    mock_client.get_llm_api_key.return_value = "llm-key-123"
                    mock_client.get_user_settings.return_value = {
                        "agent": "CodeActAgent"
                    }

                    mock_create_agent.side_effect = Exception("Agent creation failed")

                    result = await fetch_user_data_after_oauth(server_url, api_key)

                    # Should still return data even if agent creation fails
                    expected_result = {
                        "llm_api_key": "llm-key-123",
                        "settings": {"agent": "CodeActAgent"},
                    }
                    assert result == expected_result

    @pytest.mark.asyncio
    async def test_fetch_user_data_after_oauth_api_error(self):
        """Test user data fetching with API client error."""
        server_url = "https://api.example.com"
        api_key = "test-api-key"

        with patch(
            "openhands_cli.auth.api_client.OpenHandsApiClient"
        ) as mock_client_class:
            with patch("openhands_cli.auth.api_client._p"):
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                mock_client.get_llm_api_key.side_effect = ApiClientError("API error")

                with pytest.raises(ApiClientError, match="API error"):
                    await fetch_user_data_after_oauth(server_url, api_key)
