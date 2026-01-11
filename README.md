# OpenHands V1 CLI

A command-line interface for [OpenHands](https://github.com/All-Hands-AI/OpenHands), the AI-powered software development agent. Run OpenHands directly from your terminal with an interactive TUI, headless mode for automation, or integrate with your favorite IDE.

## Installation

### Using uv (Recommended)

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install openhands --python 3.12
```

### Executable Binary

Install the standalone binary with the install script:

```bash
curl -fsSL https://install.openhands.dev/install.sh | sh
```

### Using Docker

```bash
docker run -it \
    --pull=always \
    -e SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.openhands.dev/openhands/runtime:1.1-nikolaik \
    -e SANDBOX_USER_ID=$(id -u) \
    -e SANDBOX_VOLUMES=$SANDBOX_VOLUMES \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v ~/.openhands:/root/.openhands \
    --add-host host.docker.internal:host-gateway \
    --name openhands-cli-$(date +%Y%m%d%H%M%S) \
    python:3.12-slim \
    bash -c "pip install uv && uv tool install openhands --python 3.12 && openhands"
```

Set `SANDBOX_VOLUMES` to the directory you want OpenHands to access.

## Usage

### Quick Start

```bash
# Start the interactive TUI
openhands

# Start with a task
openhands -t "Fix the bug in auth.py"

# Start with a task from a file
openhands -f task.txt
```

The first time you run the CLI, it will guide you through configuring your LLM settings. You can also authenticate with OpenHands Cloud for easy setup:

```bash
openhands login
```

### Running Modes

| Mode | Command | Best For |
| --- | --- | --- |
| Terminal (TUI) | `openhands` | Interactive development |
| Headless | `openhands --headless -t "task"` | Scripts & automation |
| Web Interface | `openhands web` | Browser-based TUI |
| GUI Server | `openhands serve` | Full web GUI |
| IDE Integration | `openhands acp` | Zed, VS Code, JetBrains |

### IDE Integration (ACP)

OpenHands integrates with code editors via the [Agent Client Protocol (ACP)](https://agentclientprotocol.com/):

```bash
openhands acp
```

Supported IDEs:
- **Zed** - Native built-in support
- **VS Code** - Via community extension
- **JetBrains** - IntelliJ, PyCharm, WebStorm, etc.

### Resume Conversations

```bash
# List recent conversations and select one
openhands --resume

# Resume the most recent conversation
openhands --resume --last

# Resume a specific conversation by ID
openhands --resume <conversation-id>
```

## Features

### Headless Mode

Run OpenHands without the interactive UI for CI/CD pipelines and automation:

```bash
openhands --headless -t "Write unit tests for auth.py"

# With JSON output for parsing
openhands --headless --json -t "Create a Flask app"
```

### MCP Servers

Extend OpenHands capabilities with [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers:

```bash
# List configured servers
openhands mcp list

# Add a server
openhands mcp add tavily --transport stdio \
  npx -- -y mcp-remote "https://mcp.tavily.com/mcp/?tavilyApiKey=<your-api-key>"

# Enable/disable servers
openhands mcp enable <server-name>
openhands mcp disable <server-name>
```

### Confirmation Modes

Control how the agent handles actions:

```bash
# Default: ask for confirmation on each action
openhands

# Auto-approve all actions
openhands --always-approve

# LLM-based security analyzer
openhands --llm-approve
```

### Cloud Conversations

Run tasks on OpenHands Cloud:

```bash
openhands cloud -t "Fix the login bug"
```

## Controls

| Control | Description |
| --- | --- |
| `Ctrl+P` | Open command palette |
| `Esc` | Pause the running agent |
| `Ctrl+Q` or `/exit` | Exit the CLI |

## Documentation

For complete documentation, visit [docs.openhands.dev/openhands/usage/cli](https://docs.openhands.dev/openhands/usage/cli/installation).

## Contributing

We welcome contributions! See [DEVELOPMENT.md](DEVELOPMENT.md) for setup instructions.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `make lint` before committing
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.
