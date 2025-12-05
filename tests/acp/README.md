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

## Common Issues

### Session ID is null ✅ FIXED
**Symptom**: `{"jsonrpc":"2.0","id":2,"result":null}` for session/new

**Status**: This issue has been fixed in the current implementation.

**Previous Cause**: Method signature mismatch - agent method didn't match ACP library expectations (used request objects instead of kwargs)

**Solution Applied**: Updated method signature to use kwargs and return proper response object:
```python
async def new_session(self, cwd: str, mcp_servers: list[Any], **_kwargs: Any) -> NewSessionResponse:
    session_id = str(uuid.uuid4())
    # ... implementation ...
    return NewSessionResponse(session_id=session_id)  # Uses snake_case in Python
```

**Verification**: Run `python /tmp/test_acp.py` to verify that session/new returns a valid session ID.

### Parameter naming errors
**Symptom**: Method receives None or wrong values for parameters

**Cause**: Parameter names don't match what ACP library sends (camelCase vs snake_case)

**Fix**: Use snake_case in Python method signatures:
- `protocolVersion` → `protocol_version`
- `mcpServers` → `mcp_servers`
- `sessionId` → `session_id`

The ACP library handles the conversion automatically.
