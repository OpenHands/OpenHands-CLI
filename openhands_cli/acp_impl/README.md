# ACP Implementation

## What is the Agent Client Protocol (ACP)?

The [Agent Client Protocol (ACP)](https://agentclientprotocol.com/protocol/overview) is a standardized communication protocol that enables code editors and IDEs to interact with AI agents. ACP defines how clients (like code editors) and agents (like OpenHands) communicate through a JSON-RPC 2.0 interface.

For more details about the protocol, see the [ACP documentation](https://agentclientprotocol.com/protocol/overview).

## Development Guide

### Setup with Zed IDE

Follow the documentation at [OpenHands ACP Guide](https://docs.openhands.dev/openhands/usage/run-openhands/acp#zed-ide) for general setup instructions.

#### Option 1: Test with PR Branch

Add this agent configuration to test with the PR branch:

```json
"OpenHands-uvx": {
  "command": "uvx",
  "args": [
    "--from",
    "git+https://github.com/OpenHands/OpenHands-CLI.git@xw/acp-simplification",
    "openhands",
    "acp"
  ],
  "env": {}
}
```

#### Option 2: Launch Local Instance

Use this configuration to run your local development version:

```json
"OpenHands-local": {
  "command": "uv",
  "args": [
    "run",
    "--project",
    "/YOUR_LOCAL_PATH/OpenHands-CLI",
    "openhands",
    "acp"
  ],
  "env": {}
}
```

### Debugging

In Zed IDE, open ACP logs before starting a conversation:
- Press `Cmd+Shift+P`
- Search for **"dev: open acp log"**
- This visualizes all events between the ACP server and client

### Testing with JSON-RPC CLI

To reproduce errors or test manually, send JSON-RPC events directly using the test script:

```bash
uv run python scripts/acp/jsonrpc_cli.py ./dist/openhands acp
```

This interactive CLI allows you to:
- Send JSON-RPC messages as single lines
- View stdout/stderr responses
- Exit with `:q`, `:quit`, or `:exit`
