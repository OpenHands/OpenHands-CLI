from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from openhands.sdk.event import ActionEvent, MessageEvent, ObservationEvent
from openhands.sdk.event.base import Event
from openhands_cli.conversations.models import ConversationMetadata
from openhands_cli.conversations.protocols import ConversationStore


class ConversationExportError(Exception):
    """Raised when a conversation transcript cannot be exported."""


@dataclass(slots=True)
class ExportResult:
    """File paths produced by an export operation."""

    markdown_path: Path
    json_path: Path
    event_count: int


def export_conversation_transcript(
    store: ConversationStore,
    conversation_id: str,
    markdown_path: Path,
    json_path: Path,
) -> ExportResult:
    """Export a conversation to Markdown and JSON files."""

    if not store.exists(conversation_id):
        raise ConversationExportError(
            f"Conversation {conversation_id} does not exist on disk."
        )

    event_iter = store.load_events(conversation_id)
    events: list[Event] = list(event_iter or [])

    if not events:
        raise ConversationExportError(
            "Conversation does not have any events to export yet."
        )

    metadata = store.get_metadata(conversation_id)
    exported_at = datetime.now(UTC)

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    markdown_contents = _build_markdown(
        conversation_id=conversation_id,
        metadata=metadata,
        events=events,
        exported_at=exported_at,
    )
    json_payload = _build_json_payload(
        conversation_id=conversation_id,
        metadata=metadata,
        events=events,
        exported_at=exported_at,
    )

    try:
        markdown_path.write_text(markdown_contents, encoding="utf-8")
        json_path.write_text(
            json.dumps(json_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError as exc:  # pragma: no cover - surfaces in notify
        raise ConversationExportError(str(exc)) from exc

    return ExportResult(
        markdown_path=markdown_path,
        json_path=json_path,
        event_count=len(events),
    )


def _build_json_payload(
    conversation_id: str,
    metadata: ConversationMetadata | None,
    events: Sequence[Event],
    exported_at: datetime,
) -> dict:
    """Create the JSON payload saved to disk."""

    last_timestamp = events[-1].timestamp if events else None

    return {
        "conversation_id": conversation_id,
        "title": metadata.title if metadata else None,
        "created_at": _format_datetime(metadata.created_at if metadata else None),
        "last_modified": _format_datetime(last_timestamp),
        "exported_at": _format_datetime(exported_at),
        "events": [event.model_dump(mode="json") for event in events],
    }


def _build_markdown(
    conversation_id: str,
    metadata: ConversationMetadata | None,
    events: Sequence[Event],
    exported_at: datetime,
) -> str:
    """Create a Markdown transcript of the conversation."""

    lines: list[str] = ["# Conversation Export", ""]
    lines.append(f"- Conversation ID: `{conversation_id}`")

    if metadata and metadata.title:
        lines.append(f"- Title: {metadata.title}")

    lines.append(
        f"- Created: {_format_datetime(metadata.created_at if metadata else None)}"
    )
    last_timestamp = events[-1].timestamp if events else None
    lines.append(f"- Last event: {_format_datetime(last_timestamp)}")
    lines.append(f"- Exported: {_format_datetime(exported_at)}")
    lines.append("")
    lines.append("## Transcript")
    lines.append("")

    for event in events:
        lines.extend(_format_event_block(event))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_event_block(event: Event) -> Iterable[str]:
    """Format a single event as Markdown."""

    timestamp = _format_datetime(event.timestamp)

    if isinstance(event, MessageEvent):
        role = (event.llm_message.role or event.source or "message").capitalize()
        header = f"### {timestamp} — {role}"
        body = _stringify_message_content(event.llm_message.content)
        return [header, "", body or "_(no text provided)_"]

    if isinstance(event, ActionEvent):
        tool_name = event.tool_name or "Unnamed tool"
        header = f"### {timestamp} — Tool call ({tool_name})"
        parts = [header, ""]
        summary = event.summary or event.reasoning_content
        if summary:
            parts.append(summary)
            parts.append("")
        command = getattr(event.action, "command", None)
        if command:
            parts.append(f"`{command}`")
            parts.append("")
        action_payload = _dump_serializable(event.action)
        if action_payload:
            parts.append("```json")
            parts.append(json.dumps(action_payload, indent=2, sort_keys=True))
            parts.append("```")
        return parts

    if isinstance(event, ObservationEvent):
        tool_name = event.tool_name or "Tool result"
        header = f"### {timestamp} — Observation ({tool_name})"
        observation_text = _stringify_observation(event.observation)
        return [header, "", observation_text]

    event_dump = json.dumps(event.model_dump(mode="json"), indent=2, sort_keys=True)
    return [
        f"### {timestamp} — {event.kind}",
        "",
        "```json",
        event_dump,
        "```",
    ]


def _stringify_message_content(content: list) -> str:
    """Convert LLM message content blocks into a readable string."""

    segments: list[str] = []
    for block in content or []:
        block_dict = _dump_serializable(block)
        if isinstance(block_dict, dict):
            block_type = block_dict.get("type")
            if block_type == "text" and block_dict.get("text"):
                segments.append(str(block_dict["text"]))
            elif block_type in {"image_url", "image"}:
                image_url = block_dict.get("image_url") or block_dict.get("url")
                if isinstance(image_url, dict):
                    image_url = image_url.get("url")
                if image_url:
                    segments.append(f"[Image: {image_url}]")
            else:
                segments.append(json.dumps(block_dict, indent=2, sort_keys=True))
        else:
            segments.append(str(block))

    return "\n\n".join(segments).strip()


def _stringify_observation(observation) -> str:
    """Convert tool observations to readable text."""

    if isinstance(observation, str):
        if "\n" in observation:
            return f"```\n{observation.strip()}\n```"
        return observation

    observation_payload = _dump_serializable(observation)
    return json.dumps(observation_payload, indent=2, sort_keys=True)


def _dump_serializable(value):
    """Best-effort conversion of SDK objects to serializable dicts."""

    if value is None:
        return None

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    if hasattr(value, "__dict__"):
        return {
            key: _dump_serializable(val)
            for key, val in value.__dict__.items()
            if not key.startswith("_")
        }

    if isinstance(value, list | tuple):
        return [_dump_serializable(item) for item in value]

    if isinstance(value, dict):
        return {key: _dump_serializable(val) for key, val in value.items()}

    return value


def _format_datetime(value: datetime | str | None) -> str:
    if value is None:
        return "Unknown"

    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
