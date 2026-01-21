from __future__ import annotations

from collections.abc import Iterator

from openhands.sdk import Event
from openhands_cli.conversations.models import ConversationMetadata
from openhands_cli.conversations.protocols import ConversationStore


class CloudStore(ConversationStore):
    """
    Cloud-based implementation of the ConversationStore.

    This provider interacts with the OpenHands Cloud API to manage conversations,
    replacing direct file system access with network requests.

    Future implementation details:
    - Should authorize using the session token from `openhands_cli.auth`
    - Should implement local caching of remote events for performance
    - Maps API responses to `ConversationMetadata` and `Event` objects
    """

    def list_conversations(self, limit: int = 100) -> list[ConversationMetadata]:
        # TODO: Implement API call to GET /conversations
        raise NotImplementedError("Cloud storage is not yet implemented")

    def get_metadata(self, conversation_id: str) -> ConversationMetadata | None:
        # TODO: Implement API call to GET /conversations/{id}
        raise NotImplementedError("Cloud storage is not yet implemented")

    def get_event_count(self, conversation_id: str) -> int:
        # TODO: Implement API call to get event count
        raise NotImplementedError("Cloud storage is not yet implemented")

    def load_events(
        self,
        conversation_id: str,
        limit: int | None = None,
        start_from_newest: bool = False,
    ) -> Iterator[Event]:
        # TODO: Implement API call to GET /conversations/{id}/events (streaming)
        raise NotImplementedError("Cloud storage is not yet implemented")

    def exists(self, conversation_id: str) -> bool:
        # TODO: Check existence via API
        raise NotImplementedError("Cloud storage is not yet implemented")

    def create(self, conversation_id: str | None = None) -> str:
        # TODO: Implement API call to POST /conversations
        raise NotImplementedError("Cloud storage is not yet implemented")
