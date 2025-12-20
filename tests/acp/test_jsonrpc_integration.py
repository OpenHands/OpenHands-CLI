"""Integration tests for ACP JSON-RPC protocol compliance.

These tests verify that the ACP agent correctly handles JSON-RPC messages
as they would be sent by real clients like Zed, Toad, etc.
"""

import json
import subprocess

import pytest


@pytest.fixture
def acp_executable():
    """Get path to the ACP executable for testing."""
    # Use `uv run openhands acp` for testing
    return ["uv", "run", "openhands", "acp"]


def send_jsonrpc_message(proc: subprocess.Popen, message: dict) -> dict | None:
    """Send a JSON-RPC message and wait for response.

    This function skips notifications (messages without 'id') and returns
    the first response message that matches the request ID.
    """
    if not proc.stdin or not proc.stdout:
        return None

    msg_json = json.dumps(message) + "\n"
    proc.stdin.write(msg_json.encode())
    proc.stdin.flush()

    # Read response, skipping notifications
    request_id = message.get("id")
    while True:
        line = proc.stdout.readline()
        if not line:
            return None

        response = json.loads(line.decode())

        # If this is a notification (no id), skip it
        if "id" not in response and "method" in response:
            continue

        # If this is the response we're waiting for, return it
        if request_id is None or response.get("id") == request_id:
            return response

        # Otherwise keep looking
        # This handles out-of-order responses (shouldn't happen but be safe)
        continue


def test_jsonrpc_initialize(acp_executable):
    """Test that initialize returns correct structure."""
    proc = subprocess.Popen(
        acp_executable,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Send initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": True, "writeTextFile": True},
                    "terminal": True,
                },
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        response = send_jsonrpc_message(proc, init_msg)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response

        result = response["result"]
        assert result["protocolVersion"] == 1
        assert "agentInfo" in result
        assert result["agentInfo"]["name"] == "OpenHands CLI ACP Agent"
        assert "agentCapabilities" in result
        assert result["agentCapabilities"]["loadSession"] is True

    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_jsonrpc_session_new_returns_session_id(acp_executable, tmp_path):
    """Test that session/new returns a valid session ID."""
    proc = subprocess.Popen(
        acp_executable,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Initialize first
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": 1,
                "clientCapabilities": {"fs": {}, "terminal": True},
                "clientInfo": {"name": "test", "version": "1.0.0"},
            },
        }
        init_response = send_jsonrpc_message(proc, init_msg)
        assert init_response is not None
        assert "result" in init_response

        # Create new session
        new_session_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "session/new",
            "params": {"cwd": str(tmp_path), "mcpServers": []},
        }

        response = send_jsonrpc_message(proc, new_session_msg)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response

        result = response["result"]
        # The critical assertion: session/new MUST return sessionId
        assert "sessionId" in result
        assert result["sessionId"] is not None
        assert isinstance(result["sessionId"], str)
        assert len(result["sessionId"]) > 0

        # Verify it's a valid UUID format
        import uuid

        session_uuid = uuid.UUID(result["sessionId"])
        assert str(session_uuid) == result["sessionId"]

    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_jsonrpc_error_handling(acp_executable):
    """Test that errors are properly formatted as JSON-RPC errors."""
    proc = subprocess.Popen(
        acp_executable,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Send invalid method
        invalid_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "nonexistent/method",
            "params": {},
        }

        response = send_jsonrpc_message(proc, invalid_msg)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        # Should have error, not result
        assert "error" in response
        assert "result" not in response

        error = response["error"]
        assert "code" in error
        assert "message" in error

    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_jsonrpc_null_result_regression(acp_executable, tmp_path):
    """Regression test: Ensure session/new doesn't return null result.

    This was the original bug reported:
    session/new was returning {"jsonrpc":"2.0","id":2,"result":null}
    instead of returning a session ID.
    """
    proc = subprocess.Popen(
        acp_executable,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": True, "writeTextFile": True},
                    "terminal": True,
                    "_meta": {"terminal_output": True, "terminal-auth": True},
                },
                "clientInfo": {"name": "zed", "title": "Zed", "version": "0.212.7"},
            },
        }
        init_response = send_jsonrpc_message(proc, init_msg)
        assert init_response is not None
        assert init_response["result"] is not None

        # Create session - this is where the bug was
        new_session_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "session/new",
            "params": {"cwd": str(tmp_path), "mcpServers": []},
        }

        response = send_jsonrpc_message(proc, new_session_msg)

        # THE CRITICAL REGRESSION CHECK
        # result must NOT be null
        assert response is not None, f"No response received: {response}"
        assert "result" in response or "error" in response, (
            f"Invalid response (no result or error): {response}"
        )

        if "error" in response:
            pytest.fail(f"session/new returned error: {response['error']}")

        assert response["result"] is not None, (
            f"session/new returned null result: {response}"
        )

        # result must contain sessionId
        assert "sessionId" in response["result"], (
            f"session/new result missing sessionId: {response['result']}"
        )

        # sessionId must not be null
        assert response["result"]["sessionId"] is not None, (
            f"session/new sessionId is null: {response['result']}"
        )

    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_parameter_naming_conventions(acp_executable, tmp_path):
    """Test that parameter naming follows ACP protocol (camelCase in JSON-RPC)."""
    proc = subprocess.Popen(
        acp_executable,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": 1,  # camelCase
                "clientCapabilities": {},  # camelCase
                "clientInfo": {"name": "test", "version": "1.0.0"},  # camelCase
            },
        }
        init_response = send_jsonrpc_message(proc, init_msg)
        assert init_response is not None
        assert "result" in init_response

        # Verify response uses camelCase
        result = init_response["result"]
        assert "protocolVersion" in result  # Not protocol_version
        assert "agentInfo" in result  # Not agent_info
        assert "agentCapabilities" in result  # Not agent_capabilities

        # Create session with camelCase parameters
        new_session_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "session/new",
            "params": {
                "cwd": str(tmp_path),
                "mcpServers": [],  # camelCase
            },
        }
        session_response = send_jsonrpc_message(proc, new_session_msg)
        assert session_response is not None
        assert "result" in session_response

        # Verify response uses camelCase
        session_result = session_response["result"]
        assert "sessionId" in session_result  # Not session_id

    finally:
        proc.terminate()
        proc.wait(timeout=5)
