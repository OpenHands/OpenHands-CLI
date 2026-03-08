import os


def get_persistence_dir() -> str:
    """Get the persistence directory for storing agent settings and CLI configuration.

    Can be overridden via OPENHANDS_PERSISTENCE_DIR environment variable.
    """
    return os.environ.get(
        "OPENHANDS_PERSISTENCE_DIR", os.path.expanduser("~/.openhands")
    )


def get_conversations_dir() -> str:
    """Get the conversations directory for storing conversation data.

    Can be overridden via OPENHANDS_CONVERSATIONS_DIR environment variable.
    """
    return os.environ.get(
        "OPENHANDS_CONVERSATIONS_DIR",
        os.path.join(get_persistence_dir(), "conversations"),
    )


def get_work_dir() -> str:
    """Get the working directory for agent operations.

    Can be overridden via OPENHANDS_WORK_DIR environment variable.
    """
    return os.environ.get("OPENHANDS_WORK_DIR", os.getcwd())


# Static configuration values (don't need to be dynamic)
AGENT_SETTINGS_PATH = "agent_settings.json"

# MCP configuration file (relative to persistence dir)
MCP_CONFIG_FILE = "mcp.json"

# Plugin marketplaces configuration file
MARKETPLACES_FILE = os.path.join(PERSISTENCE_DIR, "marketplaces.json")
