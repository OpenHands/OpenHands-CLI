"""Transport-level tests for OpenHandsApiClient using respx.

These tests let the real client code execute (path building, headers,
response parsing) and only mock HTTP at the transport layer.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from openhands_cli.auth.api_client import (
    OpenHandsApiClient,
    UnauthenticatedError,
)


MOCK_RESPONSES = Path(__file__).parent / "mock_responses"
SERVER = "https://app.test.dev"
API_KEY = "test-key"
TASK_ID = "a1b2c3d4e5f6789012345678901234ab"


def _load(name: str) -> dict:
    return json.loads((MOCK_RESPONSES / name).read_text())


@pytest.fixture
def client() -> OpenHandsApiClient:
    return OpenHandsApiClient(SERVER, API_KEY)


# ----------------------------
# create_conversation
# ----------------------------


@respx.mock
@pytest.mark.asyncio
async def test_create_conversation_sends_correct_request(client):
    pending = _load("start_task_pending.json")
    route = respx.post(f"{SERVER}/api/v1/app-conversations").mock(
        return_value=httpx.Response(200, json=pending)
    )

    payload = {
        "initial_message": {"content": [{"type": "text", "text": "hello"}]},
        "selected_repository": "owner/repo",
    }
    resp = await client.create_conversation(json_data=payload)

    assert route.called
    req = route.calls.last.request
    assert req.headers["authorization"] == f"Bearer {API_KEY}"
    assert json.loads(req.content) == payload
    assert resp.json()["id"] == TASK_ID
    assert resp.json()["status"] == "WORKING"


# ----------------------------
# get_start_task_status
# ----------------------------


@respx.mock
@pytest.mark.asyncio
async def test_get_start_task_status_ready(client):
    ready = _load("start_task_ready.json")
    route = respx.get(
        f"{SERVER}/api/v1/app-conversations/start-tasks",
        params={"ids": TASK_ID},
    ).mock(return_value=httpx.Response(200, json=[ready]))

    result = await client.get_start_task_status(TASK_ID)

    assert route.called
    assert result["status"] == "READY"
    assert result["app_conversation_id"] == "conv-001"


@respx.mock
@pytest.mark.asyncio
async def test_get_start_task_status_error(client):
    error = _load("start_task_error.json")
    respx.get(
        f"{SERVER}/api/v1/app-conversations/start-tasks",
        params={"ids": TASK_ID},
    ).mock(return_value=httpx.Response(200, json=[error]))

    result = await client.get_start_task_status(TASK_ID)

    assert result["status"] == "ERROR"
    assert result["detail"] == "sandbox provisioning failed"


@respx.mock
@pytest.mark.asyncio
async def test_get_start_task_status_not_found(client):
    respx.get(
        f"{SERVER}/api/v1/app-conversations/start-tasks",
        params={"ids": TASK_ID},
    ).mock(return_value=httpx.Response(200, json=[None]))

    result = await client.get_start_task_status(TASK_ID)
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_get_start_task_status_401(client):
    respx.get(
        f"{SERVER}/api/v1/app-conversations/start-tasks",
        params={"ids": TASK_ID},
    ).mock(return_value=httpx.Response(401))

    with pytest.raises(UnauthenticatedError):
        await client.get_start_task_status(TASK_ID)


# ----------------------------
# get_conversation_info
# ----------------------------


@respx.mock
@pytest.mark.asyncio
async def test_get_conversation_info_found(client):
    conv = {"id": "conv-001", "sandbox_id": "sb-1", "execution_status": "finished"}
    respx.get(
        f"{SERVER}/api/v1/app-conversations",
        params={"ids": "conv-001"},
    ).mock(return_value=httpx.Response(200, json=[conv]))

    result = await client.get_conversation_info("conv-001")

    assert result["sandbox_id"] == "sb-1"


@respx.mock
@pytest.mark.asyncio
async def test_get_conversation_info_not_found(client):
    respx.get(
        f"{SERVER}/api/v1/app-conversations",
        params={"ids": "missing"},
    ).mock(return_value=httpx.Response(200, json=[None]))

    result = await client.get_conversation_info("missing")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_get_conversation_info_401(client):
    respx.get(
        f"{SERVER}/api/v1/app-conversations",
        params={"ids": "conv-001"},
    ).mock(return_value=httpx.Response(401))

    with pytest.raises(UnauthenticatedError):
        await client.get_conversation_info("conv-001")
