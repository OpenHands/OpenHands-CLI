import hashlib
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


def get_project_id() -> str:
    """Get a unique, stable ID for the current project based on its path."""
    work_dir = os.path.abspath(os.path.realpath(get_work_dir()))
    return hashlib.sha256(work_dir.encode("utf-8")).hexdigest()


def get_project_dir() -> str:
    """Get the persistence directory for the current project."""
    return os.path.join(get_persistence_dir(), "projects", get_project_id())


def get_prompt_history_path() -> str:
    """Get the path to the prompt history file for the current project."""
    return os.path.join(get_project_dir(), "prompt_history.json")


# Static configuration values (don't need to be dynamic)
AGENT_SETTINGS_PATH = "agent_settings.json"

# MCP configuration file (relative to persistence dir)
MCP_CONFIG_FILE = "mcp.json"
