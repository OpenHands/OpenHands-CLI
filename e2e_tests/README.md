# E2E Tests for OpenHands CLI

This directory contains end-to-end tests for the OpenHands CLI executable built by PyInstaller.

## Structure

- `models.py` - Pydantic models for test results (`TestResult` and `TestSummary`)
- `runner.py` - Test runner that coordinates all tests and provides summary reporting
- `test_version.py` - Tests the `--version` flag functionality
- `test_experimental_ui.py` - Tests the textual UI functionality
- `test_acp.py` - Tests the ACP server functionality with JSON-RPC messages

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