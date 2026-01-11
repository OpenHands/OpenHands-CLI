"""Cloud conversation listing utilities."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel

from openhands_cli.auth.api_client import OpenHandsApiClient


class CloudConversationInfo(BaseModel):
    """Minimal info needed to show a cloud conversation in the History panel."""

    id: str
    created_date: datetime
    title: str | None = None
    runtime_host: str | None = None
    session_api_key: str | None = None


def _extract_runtime_host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(str(url))
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return None


class CloudConversationLister:
    """List OpenHands Cloud conversations for the authenticated user."""

    def __init__(self, server_url: str, api_key: str):
        self.server_url = server_url
        self.api_key = api_key

    async def _list_async(self) -> list[CloudConversationInfo]:
        client = OpenHandsApiClient(self.server_url, self.api_key)
        data = await client.list_conversations()

        # Accept:
        # - {"conversations": [...]} (legacy)
        # - {"results": [...]} (current cloud API)
        # - [...] (already a list)
        conversations: list[dict[str, Any]]
        if isinstance(data, list):
            conversations = data
        else:
            conversations = list(
                data.get("results", data.get("conversations", []))  # type: ignore[arg-type]
            )

        results: list[CloudConversationInfo] = []
        for item in conversations:
            conv_id = str(
                item.get("conversation_id")
                or item.get("id")
                or item.get("conversationId")
                or ""
            )
            if not conv_id:
                continue

            created_raw = (
                item.get("created_at")
                or item.get("createdAt")
                or item.get("created_date")
                or item.get("createdDate")
                or item.get("timestamp")
            )
            try:
                created_date = datetime.fromisoformat(
                    str(created_raw).replace("Z", "+00:00")
                )
            except Exception:
                created_date = datetime.now(UTC)

            # Keep cloud timestamps timezone-aware (UTC) so relative time works
            # regardless of the user's local timezone.
            if created_date.tzinfo is None:
                created_date = created_date.replace(tzinfo=UTC)
            else:
                created_date = created_date.astimezone(UTC)

            title = item.get("title") or item.get("name") or item.get("preview")
            runtime_host = _extract_runtime_host(item.get("url"))
            session_api_key = item.get("session_api_key") or item.get("sessionApiKey")
            results.append(
                CloudConversationInfo(
                    id=conv_id,
                    created_date=created_date,
                    title=title,
                    runtime_host=runtime_host,
                    session_api_key=session_api_key,
                )
            )

        # Newest first
        results.sort(key=lambda r: r.created_date, reverse=True)
        return results

    def list(self) -> list[CloudConversationInfo]:
        """Synchronous wrapper for listing cloud conversations.

        Note: This is intended to be called from UI code that is already
        running in a background thread (or best-effort).
        """
        return asyncio.run(self._list_async())
