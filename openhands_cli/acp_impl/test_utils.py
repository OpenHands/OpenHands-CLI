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
import select
import subprocess
import time
from typing import Any


def send_jsonrpc_and_wait(
    proc: subprocess.Popen,
    message: dict[str, Any],
    timeout: float = 5.0,
) -> tuple[bool, dict[str, Any] | None, str]:
    """
    Send a JSON-RPC message and wait for response.

    Args:
        proc: The subprocess to communicate with
        message: JSON-RPC message dict
        timeout: Timeout in seconds

    Returns:
        tuple of (success: bool, response: dict | None, error_message: str)
    """
    if not proc.stdin or not proc.stdout:
        return False, None, "stdin or stdout not available"

    # Send message
    try:
        msg_line = json.dumps(message) + "\n"
        proc.stdin.write(msg_line)
        proc.stdin.flush()
    except Exception as e:
        return False, None, f"Failed to send message: {e}"

    # Wait for response
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False, None, "Process terminated unexpectedly"

        rlist, _, _ = select.select([proc.stdout], [], [], 0.5)
        if rlist:
            line = proc.stdout.readline()
            if line:
                try:
                    response = json.loads(line)
                    return True, response, ""
                except json.JSONDecodeError as e:
                    return (
                        False,
                        None,
                        f"Failed to parse JSON: {e}\nRaw: {line.strip()}",
                    )

    return False, None, "Response timeout"


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
        text=True,
        bufsize=1,
    )

    all_responses = []
    all_passed = True

    try:
        for i, msg in enumerate(messages, 1):
            if verbose:
                print(
                    f"\n📤 Message {i}/{len(messages)}: {msg.get('method', 'unknown')}"
                )

            success, response, error = send_jsonrpc_and_wait(
                proc, msg, timeout_per_message
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
