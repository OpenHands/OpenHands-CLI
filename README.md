<a name="readme-top"></a>

<div align="center">
  <img src="https://raw.githubusercontent.com/OpenHands/docs/main/openhands/static/img/logo.png" alt="Logo" width="200">
  <h1 align="center">OpenHands V1 CLI</h1>
  <h4>(Powered by <a href="https://github.com/OpenHands/software-agent-sdk">OpenHands Software Agent SDK</a>)</h4>
</div>


<div align="center">
  <a href="https://github.com/OpenHands/software-agent-sdk/blob/main/LICENSE"><img src="https://img.shields.io/github/license/OpenHands/software-agent-sdk?style=for-the-badge&color=blue" alt="MIT License"></a>
  <a href="https://openhands.dev/joinslack"><img src="https://img.shields.io/badge/Slack-Join%20Us-red?logo=slack&logoColor=white&style=for-the-badge" alt="Join our Slack community"></a>
  <br>
  <a href="https://docs.openhands.dev/openhands/usage/cli/installation"><img src="https://img.shields.io/badge/Documentation-000?logo=googledocs&logoColor=FFE165&style=for-the-badge" alt="Check out the documentation"></a> 
  <br>
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/OpenHands/OpenHands-CLI?lang=de">Deutsch</a> |
  <a href="https://www.readme-i18n.com/OpenHands/OpenHands-CLI?lang=es">Español</a> |
  <a href="https://www.readme-i18n.com/OpenHands/OpenHands-CLI?lang=fr">français</a> |
  <a href="https://www.readme-i18n.com/OpenHands/OpenHands-CLI?lang=ja">日本語</a> |
  <a href="https://www.readme-i18n.com/OpenHands/OpenHands-CLI?lang=ko">한국어</a> |
  <a href="https://www.readme-i18n.com/OpenHands/OpenHands-CLI?lang=pt">Português</a> |
  <a href="https://www.readme-i18n.com/OpenHands/OpenHands-CLI?lang=ru">Русский</a> |
  <a href="https://www.readme-i18n.com/OpenHands/OpenHands-CLI?lang=zh">中文</a>
  <hr>
</div>


The OpenHands CLI is a **lightweight, modern CLI**. It can run autonomous OpenHands agents directly in your terminal, IDE, CI pipelines, browser, etc. Easily launch local or remote sandboxed conversations.

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
| Headless | `openhands --headless -t "task"` | CI, scripts, and automation |
| Web Interface | `openhands web` | Browser-based TUI |
| GUI Server | `openhands serve` | Full web GUI |
| IDE Integration | `openhands acp` | IDEs (Toad, Zed, VSCode, JetBrains, etc) |

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

For complete documentation, visit [docs.openhands.dev/openhands/usage/cli]().

## Contributing

We welcome contributions! See [DEVELOPMENT.md](DEVELOPMENT.md) for setup instructions.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `make lint` before committing
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.
