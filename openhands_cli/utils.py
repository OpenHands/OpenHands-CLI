"""Utility functions for LLM configuration in OpenHands CLI."""

import os
from argparse import Namespace
from pathlib import Path
from typing import Any

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML
from rich.text import Text

from openhands.sdk import LLM
from openhands.tools.preset import get_default_agent


def should_set_litellm_extra_body(model_name: str) -> bool:
    """
    Determine if litellm_extra_body should be set based on the model name.

    Only set litellm_extra_body for openhands models to avoid issues
    with providers that don't support extra_body parameters.

    The SDK internally translates "openhands/" prefix to "litellm_proxy/"
    when making API calls.

    Args:
        model_name: Name of the LLM model

    Returns:
        True if litellm_extra_body should be set, False otherwise
    """
    return "openhands/" in model_name


def get_llm_metadata(
    model_name: str,
    llm_type: str,
    session_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Generate LLM metadata for OpenHands CLI.

    Args:
        model_name: Name of the LLM model
        agent_name: Name of the agent (defaults to "openhands")
        session_id: Optional session identifier
        user_id: Optional user identifier

    Returns:
        Dictionary containing metadata for LLM initialization
    """
    # Import here to avoid circular imports
    openhands_sdk_version: str = "n/a"
    try:
        import openhands.sdk

        openhands_sdk_version = openhands.sdk.__version__
    except (ModuleNotFoundError, AttributeError):
        pass

    openhands_tools_version: str = "n/a"
    try:
        import openhands.tools

        openhands_tools_version = openhands.tools.__version__
    except (ModuleNotFoundError, AttributeError):
        pass

    metadata = {
        "trace_version": openhands_sdk_version,
        "tags": [
            "app:openhands",
            f"model:{model_name}",
            f"type:{llm_type}",
            f"web_host:{os.environ.get('WEB_HOST', 'unspecified')}",
            f"openhands_sdk_version:{openhands_sdk_version}",
            f"openhands_tools_version:{openhands_tools_version}",
        ],
    }
    if session_id is not None:
        metadata["session_id"] = session_id
    if user_id is not None:
        metadata["trace_user_id"] = user_id
    return metadata


def get_default_cli_agent(llm: LLM):
    agent = get_default_agent(llm=llm, cli_mode=True)

    return agent


def create_seeded_instructions_from_args(args: Namespace) -> list[str] | None:
    """
    Build initial CLI input(s) from parsed arguments.
    """
    if getattr(args, "command", None) == "serve":
        return None

    # --file takes precedence over --task
    if getattr(args, "file", None):
        path = Path(args.file).expanduser()
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            print_formatted_text(HTML(f"<red>Failed to read file {path}: {exc}</red>"))
            raise SystemExit(1)

        initial_message = (
            "Starting this session with file context.\n\n"
            f"File path: {path}\n\n"
            "File contents:\n"
            "--------------------\n"
            f"{content}\n"
            "--------------------\n"
        )
        return [initial_message]

    if getattr(args, "task", None):
        return [args.task]

    return None


def display_json_data(data: Any) -> Text:
    """Create a Rich Text representation of JSON data (dict, list, or other types).

    This is an improved version of the SDK's display_dict function that handles
    not just dictionaries but also lists and other JSON data types.

    Fixes the issue where Linear MCP server returns JSON lists causing:
    'list' object has no attribute 'items' error.
    """
    content = Text()

    if isinstance(data, dict):
        # Handle dictionary - original display_dict behavior
        for field_name, field_value in data.items():
            if field_value is None:
                continue  # skip None fields
            content.append(f"\n  {field_name}: ", style="bold")
            if isinstance(field_value, str):
                # Handle multiline strings with proper indentation
                if "\n" in field_value:
                    content.append("\n")
                    for line in field_value.split("\n"):
                        content.append(f"    {line}\n")
                else:
                    content.append(f'"{field_value}"')
            elif isinstance(field_value, list | dict):
                content.append(str(field_value))
            else:
                content.append(str(field_value))
    elif isinstance(data, list):
        # Handle list - format as numbered items
        content.append("\n")
        for i, item in enumerate(data):
            content.append(f"  [{i}]: ", style="bold")
            if isinstance(item, str):
                if "\n" in item:
                    content.append("\n")
                    for line in item.split("\n"):
                        content.append(f"    {line}\n")
                else:
                    content.append(f'"{item}"\n')
            elif isinstance(item, list | dict):
                content.append(f"{item}\n")
            else:
                content.append(f"{item}\n")
    else:
        # Handle other types (string, number, boolean, null)
        content.append(str(data))

    return content


def apply_mcp_visualization_fix():
    """Apply monkey patch to fix MCP visualization issue.

    This fixes the issue where the SDK's display_dict function assumes input
    is always a dictionary, but Linear MCP server returns JSON lists.
    """
    import openhands.sdk.utils.visualize

    # Replace the problematic display_dict function with our improved version
    openhands.sdk.utils.visualize.display_dict = display_json_data
