"""Tests for OpenHandsCloudACPAgent authentication helper methods."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands_cli.acp_impl.agent import OpenHandsCloudACPAgent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "api_key,token_valid,expected",
    [
        pytest.param(None, False, False, id="no-api-key"),
        pytest.param("valid-key", True, True, id="valid-key"),
        pytest.param("expired-key", False, False, id="expired-key"),
    ],
)
async def test_is_authenticated(api_key, token_valid, expected):
    """Test _is_authenticated based on API key and token validity."""
    mock_conn = AsyncMock()
    with patch(
        "openhands_cli.acp_impl.agent.base_agent.TokenStorage"
    ) as mock_storage_class:
        mock_storage = MagicMock()
        mock_storage.get_api_key.return_value = api_key
        mock_storage_class.return_value = mock_storage

        agent = OpenHandsCloudACPAgent(
            conn=mock_conn,
            initial_confirmation_mode="always-ask",
        )

        with patch(
            "openhands_cli.acp_impl.agent.remote_agent.is_token_valid",
            new_callable=AsyncMock,
            return_value=token_valid,
        ):
            result = await agent._is_authenticated()
            assert result is expected
