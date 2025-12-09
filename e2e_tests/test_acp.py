"""E2E test for ACP server functionality."""

import os
import time
from pathlib import Path

from .models import TestResult


def test_acp_executable() -> TestResult:
    """Test the ACP server in the built executable with JSON-RPC messages."""
    test_name = "acp_server"
    start_time = time.time()

    try:
        # Import test utilities
        from openhands_cli.acp_impl.test_utils import test_jsonrpc_messages

        exe_path = Path("dist/openhands")
        if not exe_path.exists():
            exe_path = Path("dist/openhands.exe")
            if not exe_path.exists():
                return TestResult(
                    test_name=test_name,
                    success=False,
                    total_time_seconds=time.time() - start_time,
                    error_message="Executable not found!",
                )

        if os.name != "nt":
            os.chmod(exe_path, 0o755)

        # JSON-RPC messages to test
        test_messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": 1,
                    "clientCapabilities": {
                        "fs": {"readTextFile": True, "writeTextFile": True},
                        "terminal": True,
                        "_meta": {"terminal_output": True, "terminal-auth": True},
                    },
                    "clientInfo": {"name": "zed", "title": "Zed", "version": "0.212.7"},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "session/new",
                "params": {
                    "cwd": "/tmp",
                    "mcpServers": [],
                },
            },
        ]

        # Run the test
        success, responses = test_jsonrpc_messages(
            str(exe_path),
            ["acp"],
            test_messages,
            timeout_per_message=20.0,  # Increased timeout for CI environments
            verbose=True,
        )

        total_time = time.time() - start_time

        if success:
            return TestResult(
                test_name=test_name,
                success=True,
                total_time_seconds=total_time,
                metadata={
                    "messages_sent": len(test_messages),
                    "responses_received": len(responses),
                    "acp_server_working": True,
                },
            )
        else:
            return TestResult(
                test_name=test_name,
                success=False,
                total_time_seconds=total_time,
                error_message="ACP server test failed",
                metadata={
                    "messages_sent": len(test_messages),
                    "responses_received": len(responses),
                },
            )

    except ImportError as e:
        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=time.time() - start_time,
            error_message=f"Failed to import ACP test utilities: {e}",
        )
    except Exception as e:
        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=time.time() - start_time,
            error_message=f"Error testing ACP server: {e}",
        )
