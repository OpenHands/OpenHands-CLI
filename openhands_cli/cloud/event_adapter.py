"""Cloud runtime event -> OpenHands SDK Event adapter.

The local TUI uses `ConversationVisualizer` which expects OpenHands SDK `Event`
objects (MessageEvent/ActionEvent/ObservationEvent/...).

Cloud runtime currently streams plain dict payloads (via Socket.IO "oh_event").
To keep rendering consistent between local and cloud conversations we adapt the
runtime payloads into SDK events and feed them into the same visualizer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from openhands.sdk import Message, MessageEvent, TextContent
from openhands.sdk.event.base import Event
from openhands.sdk.event.conversation_error import ConversationErrorEvent


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def adapt_cloud_runtime_event(payload: dict[str, Any]) -> Event | None:
    """Adapt a cloud runtime payload to an OpenHands SDK Event.

    Supported:
    - User/agent chat messages -> MessageEvent
    - Conversation errors (if payload already matches) -> ConversationErrorEvent

    Everything else (environment/tool state noise) returns None by default.
    """
    # If cloud already sends OpenHands-style events with `kind`, try to parse
    # the ones we care about.
    kind = payload.get("kind")
    if kind == "MessageEvent":
        try:
            return MessageEvent(**payload)
        except Exception:
            return None
    if kind == "ConversationErrorEvent":
        try:
            return ConversationErrorEvent(**payload)
        except Exception:
            return None

    # Runtime-style payloads (observed):
    # { "source": "user"|"agent"|"environment", "action": "...",
    #   "args": {...}, "message": "..." }
    source = str(payload.get("source") or "")
    action = str(payload.get("action") or "")
    message = str(payload.get("message") or "").strip()
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}

    # Best-effort error mapping (some runtimes emit {code, detail} without `kind`)
    if isinstance(payload.get("code"), str) and isinstance(payload.get("detail"), str):
        source_raw = payload.get("source")
        source_typed: Literal["agent", "user", "environment"] = "environment"
        if source_raw in ("agent", "user", "environment"):
            source_typed = source_raw
        try:
            return ConversationErrorEvent(
                id=str(payload.get("id") or uuid4()),
                timestamp=str(payload.get("timestamp") or _now_iso()),
                source=source_typed,
                code=str(payload.get("code")),
                detail=str(payload.get("detail")),
            )
        except Exception:
            return None

    if source == "user":
        text = (
            str(args.get("content") or "").strip() if isinstance(args, dict) else ""
        ) or message
        if not text:
            return None
        return MessageEvent(
            id=str(payload.get("id") or uuid4()),
            timestamp=str(payload.get("timestamp") or _now_iso()),
            source="user",
            llm_message=Message(role="user", content=[TextContent(text=text)]),
        )

    if source == "agent":
        # Runtime uses 'message' and sometimes 'finish' for assistant output.
        text = message
        if not text and action in ("message", "finish"):
            text = (
                str(args.get("content") or "").strip() if isinstance(args, dict) else ""
            )
        if not text:
            return None
        return MessageEvent(
            id=str(payload.get("id") or uuid4()),
            timestamp=str(payload.get("timestamp") or _now_iso()),
            source="agent",
            llm_message=Message(role="assistant", content=[TextContent(text=text)]),
        )

    return None
