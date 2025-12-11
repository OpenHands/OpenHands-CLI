"""
Utilities for testing JSON-RPC servers (ACP testing).

This module provides reusable functions for testing JSON-RPC servers,
specifically designed for testing the Agent Client Protocol (ACP) implementation.

Usage:
    from openhands_cli.acp_impl.test_utils import test_jsonrpc_messages

    success, responses = test_jsonrpc_messages(
        "./dist/openhands",
        ["acp"],
        messages,
        timeout_per_message=5.0,
        verbose=True,
    )
"""

import json
import os
import select
import subprocess
import time
from typing import Any


class UnbufferedJsonRpcReader:
    """Read JSON-RPC messages from a subprocess using unbuffered I/O.

    Uses raw bytes mode with os.read() to avoid Python's text buffering issues
    that can cause messages to get stuck in buffers.
    """

    def __init__(self, stdout):
        self.stdout = stdout
        self.buffer = b""
        self.fd = stdout.fileno()

    def read_message(self, timeout: float = 5.0) -> dict[str, Any] | None:
        """Read a single JSON-RPC message (one line) from stdout.

        Args:
            timeout: Maximum time to wait for a message

        Returns:
            Parsed JSON dict, or None if timeout/error
        """
        deadline = time.time() + timeout

        while time.time() < deadline:
            # Check if we already have a complete line in the buffer
            if b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                if line:
                    return json.loads(line.decode("utf-8"))
                continue

            # Wait for more data
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            rlist, _, _ = select.select([self.stdout], [], [], min(0.5, remaining))
            if rlist:
                chunk = os.read(self.fd, 65536)
                if chunk:
                    self.buffer += chunk
                else:
                    break  # EOF

        return None


def send_jsonrpc_and_wait(
    proc: subprocess.Popen,
    message: dict[str, Any],
    timeout: float = 5.0,
    verbose: bool = False,
    reader: UnbufferedJsonRpcReader | None = None,
) -> tuple[bool, dict[str, Any] | None, str, UnbufferedJsonRpcReader | None]:
    """
    Send a JSON-RPC message and wait for response.

    This function handles JSON-RPC 2.0 notifications that may arrive before
    the actual response. Notifications have a 'method' field but no 'id',
    while responses have an 'id' field matching the request.

    Args:
        proc: The subprocess to communicate with
        message: JSON-RPC message dict
        timeout: Timeout in seconds
        verbose: Print verbose output for debugging
        reader: Optional reader to reuse (for buffering between calls)

    Returns:
        tuple of (success, response, error_message, reader)
    """
    if not proc.stdin or not proc.stdout:
        return False, None, "stdin or stdout not available", None

    # Create or reuse reader
    if reader is None:
        reader = UnbufferedJsonRpcReader(proc.stdout)

    # Send message
    try:
        msg_bytes = (json.dumps(message) + "\n").encode("utf-8")
        proc.stdin.write(msg_bytes)
        proc.stdin.flush()
    except Exception as e:
        return False, None, f"Failed to send message: {e}", reader

    # Get the request id to match with response
    request_id = message.get("id")

    # Wait for response, skipping notifications
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False, None, "Process terminated unexpectedly", reader

        remaining = deadline - time.time()
        if remaining <= 0:
            break

        response = reader.read_message(timeout=min(1.0, remaining))
        if response is None:
            continue

        # Check if this is a notification (has 'method' but no 'id')
        # JSON-RPC 2.0: notifications don't have an 'id' field
        if "method" in response and "id" not in response:
            if verbose:
                method = response.get("method", "unknown")
                print(f"  📬 Notification received: {method} (skipping)")
            # Continue waiting for the actual response
            continue

        # Check if this is the response we're waiting for
        if "id" in response:
            if request_id is not None and response["id"] != request_id:
                if verbose:
                    print(
                        f"  ⚠️  Response id mismatch: expected {request_id}"
                        f", got {response['id']}"
                    )
                continue
            return True, response, "", reader

        # Unknown message format
        return (
            False,
            response,
            f"Unknown message format: {json.dumps(response)[:100]}",
            reader,
        )

    return False, None, "Response timeout", reader


def validate_jsonrpc_response(response: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate a JSON-RPC response for errors.

    Args:
        response: The JSON-RPC response dict

    Returns:
        tuple of (is_valid: bool, error_message: str)
    """
    if "error" in response:
        error = response["error"]
        code = error.get("code", "unknown")
        message = error.get("message", "unknown")
        return False, f"JSON-RPC Error {code}: {message}"

    if "result" not in response:
        return False, "Response missing 'result' field"

    return True, ""


def test_jsonrpc_messages(
    executable_path: str,
    args: list[str],
    messages: list[dict[str, Any]],
    timeout_per_message: float = 5.0,
    verbose: bool = True,
) -> tuple[bool, list[dict[str, Any]]]:
    """
    Test a JSON-RPC server by sending messages and validating responses.

    Args:
        executable_path: Path to the executable
        args: Command-line arguments for the executable
        messages: List of JSON-RPC messages to send
        timeout_per_message: Timeout in seconds for each message
        verbose: Print detailed output

    Returns:
        tuple of (success: bool, responses: list[dict])
    """
    if verbose:
        print(f"🚀 Starting: {executable_path} {' '.join(args)}")

    proc = subprocess.Popen(
        [executable_path] + args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # Don't pipe stderr to avoid buffer blocking
        text=False,  # Use bytes mode for unbuffered I/O
        bufsize=0,  # Unbuffered
    )

    all_responses = []
    all_passed = True
    reader = None  # Reuse reader to maintain buffer between messages

    try:
        for i, msg in enumerate(messages, 1):
            if verbose:
                print(
                    f"\n📤 Message {i}/{len(messages)}: {msg.get('method', 'unknown')}"
                )

            success, response, error, reader = send_jsonrpc_and_wait(
                proc, msg, timeout_per_message, verbose=verbose, reader=reader
            )

            if not success:
                if verbose:
                    print(f"❌ {error}")
                all_passed = False
                continue

            if response:
                all_responses.append(response)

                if verbose:
                    print(f"📥 Response: {json.dumps(response)}")

                is_valid, error_msg = validate_jsonrpc_response(response)
                if not is_valid:
                    if verbose:
                        print(f"❌ {error_msg}")
                    all_passed = False
                elif verbose:
                    print("✅ Success")

        return all_passed, all_responses

    finally:
        if verbose:
            print("\n🛑 Terminating process...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
