"""E2E test for full UI functionality with mock LLM.

This test runs the complete OpenHands TUI application with a mock LLM server
to validate the full user flow:
1. User sends "echo hello world" command
2. Agent receives the request and makes a tool call to execute echo
3. Terminal executes the command
4. Agent provides final response confirming completion

Note on llm-mock (https://github.com/piyook/llm-mock):
The llm-mock project was evaluated but found unsuitable for OpenHands e2e testing
because it only provides generic lorem ipsum or stored text responses. It doesn't
support the OpenAI-compatible tool call format required by OpenHands agents.
Instead, we use a custom MockLLMServer that returns proper tool call responses.
"""

import os
import time
from pathlib import Path

from .mock_llm_server import MockLLMServer
from .models import TestResult


def test_full_ui_echo_hello_world() -> TestResult:
    """Test the full UI with echo hello world command.

    This test validates that:
    1. The TUI application starts successfully
    2. Sends "echo hello world" task to the agent
    3. Agent makes a terminal tool call to execute the echo command
    4. The command executes successfully
    5. The conversation completes with the expected output

    Returns:
        TestResult indicating success or failure
    """
    test_name = "full_ui_echo_hello_world"
    start_time = time.time()

    mock_server = None

    try:
        # Start mock LLM server
        mock_server = MockLLMServer()
        base_url = mock_server.start()

        result = _run_test_with_mock_llm(
            test_name=test_name,
            start_time=start_time,
            mock_base_url=base_url,
        )
        return result

    except Exception as e:
        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=time.time() - start_time,
            error_message=f"Error setting up test: {e}",
        )
    finally:
        if mock_server:
            mock_server.stop()


def _run_test_with_mock_llm(
    test_name: str,
    start_time: float,
    mock_base_url: str,
) -> TestResult:
    """Run the test with mock LLM server.

    Args:
        test_name: Name of the test
        start_time: Test start time
        mock_base_url: Base URL of the mock LLM server

    Returns:
        TestResult
    """

    # Set up environment with mock LLM
    # Note: We use "openai/gpt-4o-mock" as the model name because litellm
    # requires a provider prefix to route requests correctly
    env = os.environ.copy()
    env["LLM_API_KEY"] = "mock-api-key"
    env["LLM_BASE_URL"] = mock_base_url
    env["LLM_MODEL"] = "openai/gpt-4o-mock"

    # Disable confirmation prompts and enable headless mode
    exe_path = Path("dist/openhands")
    if not exe_path.exists():
        exe_path = Path("dist/openhands.exe")
        if not exe_path.exists():
            # Try running as Python module for development
            return _run_as_python_module(
                test_name=test_name,
                start_time=start_time,
                env=env,
            )

    if os.name != "nt":
        os.chmod(exe_path, 0o755)

    return _run_executable_test(
        test_name=test_name,
        start_time=start_time,
        exe_path=exe_path,
        env=env,
    )


def _run_as_python_module(
    test_name: str,
    start_time: float,
    env: dict,
) -> TestResult:
    """Run test using Python module (for development without built executable).

    Args:
        test_name: Name of the test
        start_time: Test start time
        env: Environment variables

    Returns:
        TestResult
    """
    import subprocess

    cmd = [
        "python", "-m", "openhands_cli.entrypoint",
        "--headless",
        "--json",
        "--override-with-envs",
        "--always-approve",
        "-t", "Run the command: echo hello world",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=str(Path(__file__).parent.parent),
        )

        output = proc.stdout + proc.stderr
        return _analyze_output(
            test_name=test_name,
            start_time=start_time,
            output=output,
            return_code=proc.returncode,
        )

    except subprocess.TimeoutExpired:
        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=time.time() - start_time,
            error_message="Test timed out after 120 seconds",
        )
    except Exception as e:
        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=time.time() - start_time,
            error_message=f"Error running Python module: {e}",
        )


def _run_executable_test(
    test_name: str,
    start_time: float,
    exe_path: Path,
    env: dict,
) -> TestResult:
    """Run test using built executable.

    Args:
        test_name: Name of the test
        start_time: Test start time
        exe_path: Path to executable
        env: Environment variables

    Returns:
        TestResult
    """
    import subprocess

    cmd = [
        str(exe_path),
        "--headless",
        "--json",
        "--override-with-envs",
        "--always-approve",
        "-t", "Run the command: echo hello world",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

        output = proc.stdout + proc.stderr
        return _analyze_output(
            test_name=test_name,
            start_time=start_time,
            output=output,
            return_code=proc.returncode,
        )

    except subprocess.TimeoutExpired:
        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=time.time() - start_time,
            error_message="Test timed out after 120 seconds",
        )
    except Exception as e:
        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=time.time() - start_time,
            error_message=f"Error running executable: {e}",
        )


def _analyze_output(
    test_name: str,
    start_time: float,
    output: str,
    return_code: int,
) -> TestResult:
    """Analyze test output to determine success.

    This function checks for:
    1. Terminal tool call with "echo hello world" command
    2. Successful execution (output contains "hello world")
    3. Conversation completion

    Args:
        test_name: Name of the test
        start_time: Test start time
        output: Combined stdout/stderr output
        return_code: Process return code

    Returns:
        TestResult with analysis results
    """
    import json

    total_time = time.time() - start_time

    # Check for key indicators in the output
    found_tool_call = False
    found_echo_command = False
    found_hello_world_output = False
    found_completion = False

    output_lower = output.lower()

    # Parse JSON events from the output (format: --JSON Event-- followed by JSON)
    json_events = []
    for segment in output.split("--JSON Event--"):
        segment = segment.strip()
        if segment.startswith("{"):
            # Find the end of the JSON object
            brace_count = 0
            json_end = 0
            for i, char in enumerate(segment):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break
            if json_end > 0:
                try:
                    event = json.loads(segment[:json_end])
                    json_events.append(event)
                except json.JSONDecodeError:
                    pass

    # Analyze JSON events
    for event in json_events:
        event_kind = event.get("kind", "")

        # Check for ActionEvent with terminal command
        if event_kind == "ActionEvent":
            action = event.get("action", {})
            if action.get("kind") == "TerminalAction":
                found_tool_call = True
                command = action.get("command", "")
                if "echo" in command.lower() and "hello world" in command.lower():
                    found_echo_command = True

        # Check for ObservationEvent with hello world output
        if event_kind == "ObservationEvent":
            observation = event.get("observation", {})
            content = observation.get("content", [])
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    if "hello world" in item["text"].lower():
                        found_hello_world_output = True

        # Check for completion message
        if event_kind == "MessageEvent":
            llm_message = event.get("llm_message", {})
            if llm_message.get("role") == "assistant":
                content = llm_message.get("content", "")
                if isinstance(content, str) and (
                    "completed" in content.lower() or
                    "finished" in content.lower() or
                    "successful" in content.lower()
                ):
                    found_completion = True

    # Also check for text patterns as fallback
    if "terminal" in output_lower:
        found_tool_call = True
    if "echo hello world" in output_lower or "echo 'hello world'" in output_lower:
        found_echo_command = True
    if "hello world" in output_lower:
        found_hello_world_output = True
    if "goodbye" in output_lower or return_code == 0:
        found_completion = True

    # Build metadata
    metadata = {
        "found_tool_call": found_tool_call,
        "found_echo_command": found_echo_command,
        "found_hello_world_output": found_hello_world_output,
        "found_completion": found_completion,
        "return_code": return_code,
        "json_events_count": len(json_events),
    }

    # Determine success - need all key indicators
    success = (
        found_tool_call and
        found_echo_command and
        found_hello_world_output and
        return_code == 0
    )

    if success:
        return TestResult(
            test_name=test_name,
            success=True,
            total_time_seconds=total_time,
            metadata=metadata,
            output_preview=output[-500:] if len(output) > 500 else output,
        )
    else:
        # Determine error message
        if not found_tool_call:
            error_msg = "No terminal tool call found in output"
        elif not found_echo_command:
            error_msg = "Echo command not found in tool call"
        elif not found_hello_world_output:
            error_msg = "Hello world output not found"
        elif return_code != 0:
            error_msg = f"Non-zero return code: {return_code}"
        else:
            error_msg = "Test failed for unknown reason"

        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=total_time,
            error_message=error_msg,
            metadata=metadata,
            output_preview=output[-1000:] if len(output) > 1000 else output,
        )
