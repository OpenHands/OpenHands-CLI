"""Cloud conversation listing utilities."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from openhands_cli.auth.api_client import OpenHandsApiClient


class CloudConversationInfo(BaseModel):
    """Minimal info needed to show a cloud conversation in the History panel."""

    id: str
    created_date: datetime
    title: str | None = None


class CloudConversationLister:
    """List OpenHands Cloud conversations for the authenticated user."""

    def __init__(self, server_url: str, api_key: str):
        self.server_url = server_url
        self.api_key = api_key

    async def _list_async(self) -> list[CloudConversationInfo]:
        client = OpenHandsApiClient(self.server_url, self.api_key)
        data = await client.list_conversations()

        # Accept both: {"conversations": [...]} and [...].
        conversations: list[dict[str, Any]]
        if isinstance(data, list):
            conversations = data
        else:
            conversations = list(data.get("conversations", []))

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
                created_date = datetime.now()

            title = item.get("title") or item.get("name") or item.get("preview")
            results.append(
                CloudConversationInfo(
                    id=conv_id, created_date=created_date, title=title
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
