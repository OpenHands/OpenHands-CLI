# E2E Tests for OpenHands CLI

This directory contains end-to-end tests for the OpenHands CLI executable built by PyInstaller.

## Structure

- `models.py` - Pydantic models for test results (`TestResult` and `TestSummary`)
- `runner.py` - Test runner that coordinates all tests and provides summary reporting
- `test_version.py` - Tests the `--version` flag functionality
- `test_experimental_ui.py` - Tests the textual UI functionality
- `test_acp.py` - Tests the ACP server functionality with JSON-RPC messages
- `test_full_ui.py` - Tests the full UI with mock LLM (echo hello world command)
- `mock_llm_server.py` - Mock LLM server for deterministic e2e testing

## Mock LLM Server

The `mock_llm_server.py` module provides a mock OpenAI-compatible LLM server that returns predetermined tool call responses. This enables consistent and reproducible e2e testing without requiring a real LLM.

### Why Not Use llm-mock?

The [llm-mock](https://github.com/piyook/llm-mock) project was evaluated but found **unsuitable** for OpenHands e2e testing because:

1. **No tool call support**: llm-mock only provides lorem ipsum or stored text responses. It doesn't support the OpenAI-compatible `tool_calls` format that OpenHands agents require for executing actions.

2. **No input-based routing**: llm-mock generates random or stored responses without considering the conversation context or user input. OpenHands testing requires specific responses based on the task being executed.

3. **No conversation state tracking**: The mock needs to understand when a tool has been executed and respond appropriately (e.g., finish the conversation after a successful command execution).

### Mock LLM Server Features

Our custom `MockLLMServer` provides:

- OpenAI-compatible `/chat/completions` endpoint
- Proper `tool_calls` format for terminal actions
- Input pattern matching (e.g., "echo hello world" → terminal tool call)
- Conversation state tracking (finishes after tool execution)
- Streaming and non-streaming support

### Usage Example

```python
from e2e_tests.mock_llm_server import MockLLMServer

# Start server
server = MockLLMServer()
base_url = server.start()  # Returns e.g., http://127.0.0.1:8765

# Configure environment
env = {
    "LLM_API_KEY": "mock-api-key",
    "LLM_BASE_URL": base_url,
    "LLM_MODEL": "openai/gpt-4o-mock",  # Use openai/ prefix for litellm
}

# Run your test with the mock LLM
# ...

# Stop server
server.stop()
```

## Usage

The tests are automatically run by `build.py` after building the executable. Each test returns a `TestResult` object with:

- `test_name`: Name of the test
- `success`: Whether the test passed
- `cost`: Cost of running the test (currently always 0.0)
- `boot_time_seconds`: Time to boot the application (if applicable)
- `total_time_seconds`: Total test execution time
- `error_message`: Error message if the test failed
- `output_preview`: Preview of output for debugging
- `metadata`: Additional test-specific metadata

## Running Tests Manually

```python
from e2e_tests.runner import run_all_e2e_tests, print_detailed_results

summary = run_all_e2e_tests()
print_detailed_results(summary)
```

## Adding New Tests

1. Create a new test file in this directory (e.g., `test_new_feature.py`)
2. Implement a test function that returns a `TestResult` object
3. Add the test function to the `tests` list in `runner.py`

## Full UI Test Details

The `test_full_ui.py` test validates the complete user flow:

1. Starts a mock LLM server
2. Runs the OpenHands CLI in headless mode with `--json` output
3. Sends the task: "Run the command: echo hello world"
4. Validates that:
   - A terminal tool call was made with `echo hello world`
   - The command executed successfully
   - "hello world" appears in the output
   - The conversation completes with return code 0

This test demonstrates that the full TUI application works end-to-end, from user input through LLM processing to terminal execution.