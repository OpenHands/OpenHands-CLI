"""Tests for the ACP debug logger."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

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

    def test_init_creates_log_file_with_utc_timestamp(self, temp_log_dir: Path):
        """Test that DebugLogger creates a UTC timestamped log file."""
        debug_logger = DebugLogger(log_dir=temp_log_dir)

        assert debug_logger.log_file.parent == temp_log_dir
        assert debug_logger.log_file.name.endswith("_acp.jsonl")
        # Check format: YYYYMMDD_HHMMSSZ_acp.jsonl (UTC with Z suffix)
        name_parts = debug_logger.log_file.stem.split("_")
        assert len(name_parts) == 3
        assert len(name_parts[0]) == 8  # YYYYMMDD
        assert name_parts[1].endswith("Z")  # HHMMSSZ (UTC indicator)
        assert len(name_parts[1]) == 7  # HHMMSSZ
        assert name_parts[2] == "acp"

    @pytest.mark.asyncio
    async def test_call_logs_incoming_message(self, temp_log_dir: Path):
        """Test that incoming messages are logged with >>> direction."""
        debug_logger = DebugLogger(log_dir=temp_log_dir)
        message = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        event = StreamEvent(direction=StreamDirection.INCOMING, message=message)

        await debug_logger(event)
        debug_logger.close()

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
        debug_logger.close()

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
        debug_logger.close()

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
        debug_logger.close()

        with open(debug_logger.log_file) as f:
            entry = json.loads(f.read())

        # Check timestamp format includes timezone indicator
        ts = entry["ts"]
        assert "T" in ts  # ISO format separator
        assert "+" in ts or ts.endswith("Z") or ":00" in ts  # timezone indicator

    def test_uses_default_persistence_dir(self, temp_log_dir: Path):
        """Test that DebugLogger uses default persistence dir when none provided."""
        with patch(
            "openhands_cli.acp_impl.debug_logger.get_persistence_dir",
            return_value=str(temp_log_dir),
        ):
            debug_logger = DebugLogger()

            # Should use the mocked persistence dir with acp-debug subdirectory
            assert debug_logger.log_dir == temp_log_dir / "acp-debug"
            assert "acp-debug" in str(debug_logger.log_dir)

    def test_close_handles_unopened_file(self, temp_log_dir: Path):
        """Test that close() is safe to call even if no writes occurred."""
        debug_logger = DebugLogger(log_dir=temp_log_dir)
        # Should not raise even if file was never opened
        debug_logger.close()

    @pytest.mark.asyncio
    async def test_close_flushes_and_closes_file(self, temp_log_dir: Path):
        """Test that close() properly closes the file handle."""
        debug_logger = DebugLogger(log_dir=temp_log_dir)
        event = StreamEvent(
            direction=StreamDirection.INCOMING,
            message={"jsonrpc": "2.0", "method": "test"},
        )
        await debug_logger(event)

        assert debug_logger._file_handle is not None
        debug_logger.close()
        assert debug_logger._file_handle is None
