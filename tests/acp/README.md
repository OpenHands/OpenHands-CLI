# ACP Tests

This directory contains tests for the OpenHands ACP (Agent Client Protocol) implementation.


## Running Tests

```bash
# Run all ACP tests
uv run pytest tests/acp/ -v

# Run only integration tests (recommended)
uv run pytest tests/acp/test_jsonrpc_integration.py -v

# Run specific test
uv run pytest tests/acp/test_jsonrpc_integration.py::test_jsonrpc_session_new_returns_session_id -v
```

## ACP Library Version

The project is pinned to `agent-client-protocol==0.7.0` for stability. This version:
- Uses kwargs-based method signatures instead of request objects
- Automatically converts between camelCase (JSON-RPC) and snake_case (Python)
- Provides better typing support

## Debugging ACP Issues

For debugging ACP issues, use the scripts in `scripts/acp/`:

```bash
# Interactive JSON-RPC testing
python scripts/acp/debug_client.py

# Manual JSON-RPC message sending
python scripts/acp/jsonrpc_cli.py
```

