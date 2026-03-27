<a name="readme-top"></a>

<div align="center">
  <img src="https://raw.githubusercontent.com/OpenHands/docs/main/openhands/static/img/logo.png" alt="Logo" width="200">
  <h1 align="center">OpenHands V1 CLI</h1>
  <h4>(Powered by <a href="https://github.com/OpenHands/software-agent-sdk">OpenHands Software Agent SDK</a>)</h4>
</div>


<div align="center">
  <a href="https://github.com/OpenHands/OpenHands-CLI/blob/main/LICENSE"><img src="https://img.shields.io/github/license/OpenHands/software-agent-sdk?style=for-the-badge&color=blue" alt="MIT License"></a>
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

<div align="center">
  <strong>Trusted by engineers at</strong>
  <br/><br/>
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137f6974b71a1a4a932f82_TikTok_logo.svg" alt="TikTok" height="22">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137f523b08f91a5aa905b9_Vmware.svg" alt="VMware" height="22">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137f2cb537758796a9dba1_Roche_Logo.svg" alt="Roche" height="22">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137f10c3975e28b3932320_Amazon_logo%201.svg" alt="Amazon" height="22">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137ec5a6f77dd174e557ce_C3ai_logo%201.svg" alt="C3 AI" height="22">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137eac8f27ca27f5e48420_Netflix_2015_logo%201.svg" alt="Netflix" height="22">
  <br/>
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137e8df2c028b9e1506ede_mastercard%201.svg" alt="Mastercard" height="22">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137e783790933dd06f9d59_Red_Hat_Logo_2019%201.svg" alt="Red Hat" height="22">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137e5fa006d963a1d1904d_mongodb-ar21%201.svg" alt="MongoDB" height="22">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137e47b45195da10c50f49_apple-11%201.svg" alt="Apple" height="22">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137e34e3a5ab71e37082a7_NVIDIA_logo%201.svg" alt="NVIDIA" height="22">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://cdn.prod.website-files.com/68ff4058b35616cdd47d5b59/69137e199ce2cb594b0210ab_google-ar21%201.svg" alt="Google" height="22">
</div>

<hr>

Run OpenHands agent inside your terminal, favorite IDE, CI pipelines, local browser, or secure OpenHands Cloud sandboxes.

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
The first time you run the CLI, it will guide you through configuring your LLM settings:

```bash
openhands
```


### Configuration

OpenHands CLI stores configuration under `~/.openhands/` (created on first run):

- `agent_settings.json`: persisted agent settings (including condenser config)
- `cli_config.json`: CLI/TUI preferences (e.g., critic enabled)
- `mcp.json`: MCP server configuration

By default, environment variables like `LLM_API_KEY`, `LLM_MODEL`, and `LLM_BASE_URL` are ignored; pass `--override-with-envs` to apply them (not persisted).

### Running Modes

| Mode | Command | Best For |
| --- | --- | --- |
| [Terminal (TUI)](https://docs.openhands.dev/openhands/usage/cli/terminal) | `openhands` | Interactive development |
| [IDE Integration](https://docs.openhands.dev/openhands/usage/cli/ide/overview) | `openhands acp` | IDEs (Toad, Zed, VSCode, JetBrains, etc) |
| [Headless](https://docs.openhands.dev/openhands/usage/cli/headless) | `openhands --headless -t "task"` | CI, scripts, and automation |
| [Web Interface](https://docs.openhands.dev/openhands/usage/cli/web-interface) | `openhands web` | Browser-based TUI |
| [GUI Server](https://docs.openhands.dev/openhands/usage/cli/gui-server) | `openhands serve` | [Full web GUI](https://github.com/OpenHands/OpenHands)|

## Features

### [MCP Servers](https://docs.openhands.dev/openhands/usage/cli/mcp-servers)

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

### [Confirmation Modes](https://docs.openhands.dev/openhands/usage/cli/command-reference)

Control how the agent handles actions:

```bash
# Default: ask for confirmation on each action
openhands

# Auto-approve all actions
openhands --always-approve  # or --yolo

# LLM-based security analyzer
openhands --llm-approve
```

### [Cloud Conversations](https://docs.openhands.dev/openhands/usage/cli/cloud)

Run tasks on OpenHands Cloud. First, authenticate with OpenHands Cloud to fetch your settings:

```bash
# Login to OpenHands Cloud
openhands login

# Run a task on OpenHands Cloud
openhands cloud -t "Fix the login bug"
```


### [Headless Mode](https://docs.openhands.dev/openhands/usage/cli/headless)

Run OpenHands without the interactive UI for CI/CD pipelines and automation:

```bash
openhands --headless -t "Write unit tests for auth.py"
openhands --headless -f instructions.md  # or use a file

# With JSON output for parsing
openhands --headless --json -t "Create a Flask app"
```

### Resume Conversations

```bash
openhands --resume              # list recent conversations
openhands --resume <id>         # resume specific conversation
openhands --resume --last       # resume most recent
```

## Documentation

For complete documentation, visit https://docs.openhands.dev/openhands/usage/cli.

## License

MIT License - see [LICENSE](LICENSE) for details.
