"""Tests for the ACP debug logger."""

import json
import tempfile
from pathlib import Path

import pytest
from acp.connection import StreamDirection, StreamEvent

from openhands_cli.acp_impl.debug_logger import DebugLogger


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestDebugLogger:
    """Tests for DebugLogger class."""

    def test_init_creates_log_directory(self, temp_log_dir: Path):
        """Test that DebugLogger creates the log directory on init."""
        log_dir = temp_log_dir / "custom-dir"
        assert not log_dir.exists()

        debug_logger = DebugLogger(log_dir=log_dir)

        assert log_dir.exists()
        assert debug_logger.log_dir == log_dir

    def test_init_creates_log_file_with_timestamp(self, temp_log_dir: Path):
        """Test that DebugLogger creates a timestamped log file."""
        debug_logger = DebugLogger(log_dir=temp_log_dir)

        assert debug_logger.log_file.parent == temp_log_dir
        assert debug_logger.log_file.name.endswith("_acp.jsonl")
        # Check format: YYYYMMDD_HHMMSS_acp.jsonl
        name_parts = debug_logger.log_file.stem.split("_")
        assert len(name_parts) == 3
        assert len(name_parts[0]) == 8  # YYYYMMDD
        assert len(name_parts[1]) == 6  # HHMMSS
        assert name_parts[2] == "acp"

    @pytest.mark.asyncio
    async def test_call_logs_incoming_message(self, temp_log_dir: Path):
        """Test that incoming messages are logged with >>> direction."""
        debug_logger = DebugLogger(log_dir=temp_log_dir)
        message = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        event = StreamEvent(direction=StreamDirection.INCOMING, message=message)

        await debug_logger(event)

        assert debug_logger.log_file.exists()
        with open(debug_logger.log_file) as f:
            content = f.read()
        entry = json.loads(content.strip())
        assert entry["dir"] == ">>>"
        assert entry["msg"] == message
        assert "ts" in entry

    @pytest.mark.asyncio
    async def test_call_logs_outgoing_message(self, temp_log_dir: Path):
        """Test that outgoing messages are logged with <<< direction."""
        debug_logger = DebugLogger(log_dir=temp_log_dir)
        message = {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "1.0"}}
        event = StreamEvent(direction=StreamDirection.OUTGOING, message=message)

        await debug_logger(event)

        with open(debug_logger.log_file) as f:
            content = f.read()
        entry = json.loads(content.strip())
        assert entry["dir"] == "<<<"
        assert entry["msg"] == message

    @pytest.mark.asyncio
    async def test_call_appends_multiple_messages(self, temp_log_dir: Path):
        """Test that multiple messages are appended to the same log file."""
        debug_logger = DebugLogger(log_dir=temp_log_dir)

        messages = [
            StreamEvent(
                direction=StreamDirection.INCOMING,
                message={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            ),
            StreamEvent(
                direction=StreamDirection.OUTGOING,
                message={"jsonrpc": "2.0", "id": 1, "result": {}},
            ),
            StreamEvent(
                direction=StreamDirection.INCOMING,
                message={"jsonrpc": "2.0", "id": 2, "method": "prompt"},
            ),
        ]

        for msg in messages:
            await debug_logger(msg)

        with open(debug_logger.log_file) as f:
            lines = f.readlines()

        assert len(lines) == 3
        entries = [json.loads(line) for line in lines]
        assert entries[0]["dir"] == ">>>"
        assert entries[1]["dir"] == "<<<"
        assert entries[2]["dir"] == ">>>"

    @pytest.mark.asyncio
    async def test_call_logs_timestamp_in_utc(self, temp_log_dir: Path):
        """Test that timestamps are logged in ISO format with UTC timezone."""
        debug_logger = DebugLogger(log_dir=temp_log_dir)
        event = StreamEvent(
            direction=StreamDirection.INCOMING,
            message={"jsonrpc": "2.0", "method": "test"},
        )

        await debug_logger(event)

        with open(debug_logger.log_file) as f:
            entry = json.loads(f.read())

        # Check timestamp format includes timezone indicator
        ts = entry["ts"]
        assert "T" in ts  # ISO format separator
        assert "+" in ts or ts.endswith("Z") or ":00" in ts  # timezone indicator

    def test_uses_default_persistence_dir(self):
        """Test that DebugLogger uses default persistence dir when none provided."""
        debug_logger = DebugLogger()

        # Should use ~/.openhands/acp-debug/ by default
        assert "acp-debug" in str(debug_logger.log_dir)
