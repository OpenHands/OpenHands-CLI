"""Utility functions for MCP in ACP implementation."""

from collections.abc import Sequence
from typing import Any

from acp.schema import (
    HttpMcpServer,
    SseMcpServer,
    StdioMcpServer,
)


ACPMCPServerType = StdioMcpServer | HttpMcpServer | SseMcpServer


def _convert_env_to_dict(env: Sequence[dict[str, str]]) -> dict[str, str]:
    """
    Convert environment variables from serialized EnvVariable format to a dictionary.

    When Pydantic models are dumped to dict, EnvVariable objects become dicts
    with 'name' and 'value' keys.

    Args:
        env: List of dicts with 'name' and 'value' keys (serialized EnvVariable objects)

    Returns:
        Dictionary mapping environment variable names to values
    """
    env_dict: dict[str, str] = {}
    for env_var in env:
        env_dict[env_var["name"]] = env_var["value"]
    return env_dict


def convert_acp_mcp_servers_to_agent_format(
    mcp_servers: Sequence[ACPMCPServerType],
) -> dict[str, dict[str, Any]]:
    """
    Convert MCP servers from ACP format to Agent format.

    ACP and Agent use different formats for MCP server configurations:
    - ACP: List of Pydantic server models with 'name' field, env as array of EnvVariable
    - Agent: Dict keyed by server name, env as dict

    Args:
        mcp_servers: List of MCP server Pydantic models from ACP

    Returns:
        Dictionary of MCP servers in Agent format (keyed by name)
    """
    converted_servers: dict[str, dict[str, Any]] = {}

    for server in mcp_servers:
        server_dict = server.model_dump()
        server_name: str = server_dict["name"]
        server_config: dict[str, Any] = {
            k: v for k, v in server_dict.items() if k != "name"
        }

        # Convert env from array to dict format if present
        # ACP sends env as array of EnvVariable objects, but Agent expects dict
        if "env" in server_config:
            server_config["env"] = _convert_env_to_dict(server_config["env"])
        converted_servers[server_name] = server_config

    return converted_servers
