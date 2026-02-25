"""ACP protocol debug logger that observes all JSON-RPC messages."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

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
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%SZ")
        self.log_file = self.log_dir / f"{timestamp}_acp.jsonl"
        self._file_handle: TextIO | None = None
        logger.info(f"ACP debug logging enabled: {self.log_file}")

    def _get_file_handle(self) -> TextIO:
        """Get or create the file handle for writing logs."""
        if self._file_handle is None:
            self._file_handle = open(self.log_file, "a")
        return self._file_handle

    async def __call__(self, event: StreamEvent) -> None:
        """StreamObserver callback - logs incoming/outgoing messages.

        Args:
            event: The stream event containing direction and message data
        """
        direction = ">>>" if event.direction == StreamDirection.INCOMING else "<<<"
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "dir": direction,
            "msg": event.message,
        }
        line = json.dumps(entry) + "\n"
        await asyncio.to_thread(self._write_line, line)

    def _write_line(self, line: str) -> None:
        """Write a line to the log file (runs in thread pool)."""
        f = self._get_file_handle()
        f.write(line)
        f.flush()

    def close(self) -> None:
        """Close the log file handle."""
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None
