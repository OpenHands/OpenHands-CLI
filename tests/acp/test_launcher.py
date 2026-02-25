"""Tests for the ACP server launcher."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_acp_dependencies():
    """Mock external dependencies for launcher tests."""
    with (
        patch(
            "openhands_cli.acp_impl.agent.launcher.stdio_streams"
        ) as mock_stdio_streams,
        patch("openhands_cli.acp_impl.agent.launcher.AgentSideConnection") as mock_conn,
        patch("openhands_cli.acp_impl.agent.launcher.asyncio.Event") as mock_event,
    ):
        mock_stdio_streams.return_value = (AsyncMock(), AsyncMock())
        mock_event.return_value.wait = AsyncMock(side_effect=asyncio.CancelledError)
        yield {"connection": mock_conn}


@pytest.fixture
def temp_debug_dir():
    """Create a temporary directory for debug logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cloud,patch_target",
    [
        pytest.param(
            False,
            "openhands_cli.acp_impl.agent.local_agent.LocalOpenHandsACPAgent",
            id="local",
        ),
        pytest.param(
            True,
            "openhands_cli.acp_impl.agent.launcher.OpenHandsCloudACPAgent",
            id="cloud",
        ),
    ],
)
async def test_run_acp_server_creates_correct_agent_type(
    mock_acp_dependencies, cloud: bool, patch_target: str
):
    """Test that run_acp_server creates the correct agent type based on cloud flag."""
    from openhands_cli.acp_impl.agent.launcher import run_acp_server

    with patch(patch_target) as mock_agent:
        try:
            await run_acp_server(cloud=cloud)
        except asyncio.CancelledError:
            pass

        mock_conn = mock_acp_dependencies["connection"]
        assert mock_conn.called
        factory = mock_conn.call_args[0][0]
        assert callable(factory)

        factory(MagicMock())
        mock_agent.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "confirmation_mode,resume_id,streaming",
    [
        pytest.param("always-ask", None, False, id="defaults"),
        pytest.param("always-approve", "abc-123", True, id="all-options"),
        pytest.param("llm-approve", None, True, id="llm-streaming"),
    ],
)
async def test_run_acp_server_local_agent_params(
    mock_acp_dependencies, confirmation_mode, resume_id, streaming
):
    """Test that run_acp_server passes all parameters to the local agent."""
    from openhands_cli.acp_impl.agent.launcher import run_acp_server

    with patch(
        "openhands_cli.acp_impl.agent.local_agent.LocalOpenHandsACPAgent"
    ) as mock_local:
        try:
            await run_acp_server(
                initial_confirmation_mode=confirmation_mode,
                resume_conversation_id=resume_id,
                streaming_enabled=streaming,
                cloud=False,
            )
        except asyncio.CancelledError:
            pass

        factory = mock_acp_dependencies["connection"].call_args[0][0]
        factory(MagicMock())

        mock_local.assert_called_once()
        args = mock_local.call_args[0]
        assert args[1] == confirmation_mode
        assert args[2] == resume_id
        assert args[3] == streaming


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "api_url,confirmation_mode,resume_id",
    [
        pytest.param("https://app.all-hands.dev", "always-ask", None, id="defaults"),
        pytest.param("https://custom.url", "always-approve", "xyz-789", id="custom"),
    ],
)
async def test_run_acp_server_cloud_agent_params(
    mock_acp_dependencies, api_url, confirmation_mode, resume_id
):
    """Test that run_acp_server passes all parameters to the cloud agent."""
    from openhands_cli.acp_impl.agent.launcher import run_acp_server

    with patch(
        "openhands_cli.acp_impl.agent.launcher.OpenHandsCloudACPAgent"
    ) as mock_cloud:
        try:
            await run_acp_server(
                cloud=True,
                cloud_api_url=api_url,
                initial_confirmation_mode=confirmation_mode,
                resume_conversation_id=resume_id,
            )
        except asyncio.CancelledError:
            pass

        factory = mock_acp_dependencies["connection"].call_args[0][0]
        factory(MagicMock())

        mock_cloud.assert_called_once()
        kwargs = mock_cloud.call_args[1]
        assert kwargs["cloud_api_url"] == api_url
        assert kwargs["initial_confirmation_mode"] == confirmation_mode
        assert kwargs["resume_conversation_id"] == resume_id


@pytest.mark.asyncio
async def test_run_acp_server_debug_disabled_by_default(mock_acp_dependencies):
    """Test that debug logging is disabled by default (no observers)."""
    from openhands_cli.acp_impl.agent.launcher import run_acp_server

    with patch("openhands_cli.acp_impl.agent.local_agent.LocalOpenHandsACPAgent"):
        try:
            await run_acp_server(cloud=False)
        except asyncio.CancelledError:
            pass

        mock_conn = mock_acp_dependencies["connection"]
        assert mock_conn.called
        # Check that no observers were passed (no kwargs or empty observers)
        call_kwargs = mock_conn.call_args[1] if mock_conn.call_args[1] else {}
        assert "observers" not in call_kwargs or not call_kwargs.get("observers")


@pytest.mark.asyncio
async def test_run_acp_server_debug_enabled_creates_observer(
    mock_acp_dependencies, temp_debug_dir
):
    """Test that debug=True creates a DebugLogger observer."""
    from openhands_cli.acp_impl.agent.launcher import run_acp_server

    with (
        patch("openhands_cli.acp_impl.agent.local_agent.LocalOpenHandsACPAgent"),
        patch(
            "openhands_cli.acp_impl.debug_logger.get_persistence_dir",
            return_value=str(temp_debug_dir),
        ),
    ):
        try:
            await run_acp_server(cloud=False, debug=True)
        except asyncio.CancelledError:
            pass

        mock_conn = mock_acp_dependencies["connection"]
        assert mock_conn.called
        call_kwargs = mock_conn.call_args[1]
        assert "observers" in call_kwargs
        assert len(call_kwargs["observers"]) == 1

        # Verify the observer is a DebugLogger instance
        from openhands_cli.acp_impl.debug_logger import DebugLogger

        assert isinstance(call_kwargs["observers"][0], DebugLogger)


@pytest.mark.asyncio
async def test_run_acp_server_debug_enabled_cloud_mode(
    mock_acp_dependencies, temp_debug_dir
):
    """Test that debug=True works with cloud mode."""
    from openhands_cli.acp_impl.agent.launcher import run_acp_server

    with (
        patch("openhands_cli.acp_impl.agent.launcher.OpenHandsCloudACPAgent"),
        patch(
            "openhands_cli.acp_impl.debug_logger.get_persistence_dir",
            return_value=str(temp_debug_dir),
        ),
    ):
        try:
            await run_acp_server(cloud=True, debug=True)
        except asyncio.CancelledError:
            pass

        mock_conn = mock_acp_dependencies["connection"]
        call_kwargs = mock_conn.call_args[1]
        assert "observers" in call_kwargs
        assert len(call_kwargs["observers"]) == 1
