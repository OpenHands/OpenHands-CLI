"""Unit tests for API client functionality."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from openhands_cli.auth.api_client import (
    ApiClientError,
    OpenHandsApiClient,
    UnauthenticatedError,
    create_and_save_agent_configuration,
    fetch_user_data_after_oauth,
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

    @pytest.mark.asyncio
    async def test_get_user_info_success(self):
        """Test successful user info retrieval."""
        client = OpenHandsApiClient("https://api.example.com", "test-key")

        expected_user_info = {
            "id": "user123",
            "email": "user@example.com",
            "name": "Test User",
        }

        with patch.object(client, "_get_json") as mock_get_json:
            mock_get_json.return_value = expected_user_info

            result = await client.get_user_info()

            assert result == expected_user_info
            mock_get_json.assert_called_once_with("/api/user/info")

    @pytest.mark.asyncio
    async def test_get_json_401_error(self):
        """Test JSON GET request with 401 Unauthorized error."""
        client = OpenHandsApiClient("https://api.example.com", "test-key")

        with patch.object(client, "get") as mock_get:
            from openhands_cli.auth.http_client import AuthHttpError

            mock_get.side_effect = AuthHttpError("HTTP 401: Unauthorized")

            with pytest.raises(
                UnauthenticatedError,
                match="Authentication failed for '/test': HTTP 401: Unauthorized",
            ):
                await client._get_json("/test")


class TestHelperFunctions:
    """Test cases for helper functions in api_client module."""

    def test_create_and_save_agent_configuration(self):
        """Test agent creation and saving from settings."""
        llm_api_key = "test-llm-key"
        settings = {"llm_model": "gpt-4o", "agent": "CodeActAgent", "language": "en"}

        with patch("openhands_cli.auth.api_client.AgentStore") as mock_store_class:
            with patch("openhands_cli.auth.api_client._p") as mock_print:
                mock_store = MagicMock()
                mock_agent = MagicMock()
                mock_llm = MagicMock()
                mock_llm.model = "gpt-4o"
                mock_llm.base_url = "https://api.openai.com"
                mock_llm.usage_id = "test-agent"
                mock_agent.llm = mock_llm
                mock_agent.tools = [MagicMock(), MagicMock()]
                mock_agent.condenser = MagicMock()

                mock_store.create_and_save_from_settings.return_value = mock_agent
                mock_store.load.return_value = None  # No existing agent
                mock_store_class.return_value = mock_store

                create_and_save_agent_configuration(llm_api_key, settings)

                mock_store.create_and_save_from_settings.assert_called_once_with(
                    llm_api_key=llm_api_key,
                    settings=settings,
                )
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
                "openhands_cli.auth.api_client.create_and_save_agent_configuration"
            ) as mock_create_and_save:
                with patch("openhands_cli.auth.api_client._p"):
                    mock_client = AsyncMock()
                    mock_client_class.return_value = mock_client

                    mock_client.get_llm_api_key.return_value = "llm-key-123"
                    mock_client.get_user_settings.return_value = {
                        "llm_model": "gpt-4o",
                        "agent": "CodeActAgent",
                    }

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
                    mock_create_and_save.assert_called_once()

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
                "openhands_cli.auth.api_client.create_and_save_agent_configuration"
            ) as mock_create_and_save:
                with patch("openhands_cli.auth.api_client._p"):
                    mock_client = AsyncMock()
                    mock_client_class.return_value = mock_client

                    mock_client.get_llm_api_key.return_value = "llm-key-123"
                    mock_client.get_user_settings.return_value = {
                        "agent": "CodeActAgent"
                    }

                    mock_create_and_save.side_effect = Exception(
                        "Agent creation failed"
                    )

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
