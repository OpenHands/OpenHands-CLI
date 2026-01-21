from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ConversationMetadata:
    """Metadata for a conversation."""

    id: str
    created_at: datetime
    title: str | None = None
    last_modified: datetime | None = None
