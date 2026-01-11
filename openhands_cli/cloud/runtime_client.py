"""Runtime API client for OpenHands Cloud conversations.

This client talks to the per-conversation runtime host (prod-runtime.*) using
the session API key returned by the cloud control plane.
"""

from __future__ import annotations

from typing import Any

import httpx


class CloudRuntimeClient:
    """Synchronous client for a single runtime host."""

    # Runtime rejects large limits (observed: 200 -> 400 "Invalid limit").
    MAX_EVENTS_LIMIT = 100

    def __init__(self, *, runtime_host: str, session_api_key: str) -> None:
        self._client = httpx.Client(
            base_url=runtime_host.rstrip("/"),
            headers={"X-Session-API-Key": session_api_key},
            timeout=httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0),
        )

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def get_conversation_info(self, *, conversation_id: str) -> dict[str, Any]:
        resp = self._client.get(f"/api/conversations/{conversation_id}")
        resp.raise_for_status()
        data = resp.json()
        assert isinstance(data, dict)
        return data

    def get_events(
        self,
        *,
        conversation_id: str,
        start_id: int = 0,
        end_id: int | None = None,
        reverse: bool = False,
        limit: int = MAX_EVENTS_LIMIT,
    ) -> tuple[list[dict[str, Any]], bool]:
        params: dict[str, Any] = {
            "start_id": start_id,
            "reverse": reverse,
            "limit": min(limit, self.MAX_EVENTS_LIMIT),
        }
        if end_id is not None:
            params["end_id"] = end_id

        resp = self._client.get(
            f"/api/conversations/{conversation_id}/events", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        events = data.get("events", [])
        has_more = bool(data.get("has_more", False))
        if not isinstance(events, list):
            events = []
        return events, has_more

    def send_user_message(self, *, conversation_id: str, message: str) -> None:
        resp = self._client.post(
            f"/api/conversations/{conversation_id}/message", json={"message": message}
        )
        resp.raise_for_status()
