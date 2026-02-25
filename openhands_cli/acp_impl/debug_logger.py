"""ACP protocol debug logger that observes all JSON-RPC messages."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from acp.connection import StreamDirection, StreamEvent

from openhands_cli.locations import get_persistence_dir


logger = logging.getLogger(__name__)


class DebugLogger:
    """ACP protocol debug logger that observes all JSON-RPC messages.

    Implements the StreamObserver protocol from the agent-client-protocol library
    to capture all incoming and outgoing messages and write them to a JSONL file.

    Usage:
        debug_logger = DebugLogger()
        AgentSideConnection(create_agent, writer, reader, observers=[debug_logger])
    """

    def __init__(self, log_dir: Path | None = None):
        """Initialize the debug logger.

        Args:
            log_dir: Directory to store log files. Defaults to ~/.openhands/acp-debug/
        """
        self.log_dir = log_dir or Path(get_persistence_dir()) / "acp-debug"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{timestamp}_acp.jsonl"
        logger.info(f"ACP debug logging enabled: {self.log_file}")

    async def __call__(self, event: StreamEvent) -> None:
        """StreamObserver callback - logs incoming/outgoing messages.

        Args:
            event: The stream event containing direction and message data
        """
        direction = (
            ">>>" if event.direction == StreamDirection.INCOMING else "<<<"
        )
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "dir": direction,
            "msg": event.message,
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
