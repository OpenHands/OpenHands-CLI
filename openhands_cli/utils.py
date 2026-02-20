"""Utility functions for LLM configuration in OpenHands CLI."""

import json
import os
import platform
import re
from argparse import Namespace
from pathlib import Path
from typing import Any

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands.sdk import LLM, Agent, ImageContent, TextContent
from openhands.sdk.event import SystemPromptEvent
from openhands.sdk.event.base import Event
from openhands.sdk.tool import Tool
from openhands.tools.delegate import DelegateTool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.preset.default import get_default_condenser
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool


def abbreviate_number(n: int | float) -> str:
    """Abbreviate large numbers with K/M/B suffixes.

    Examples:
        1234 -> '1.23K'
        1200000 -> '1.2M'
        2500000000 -> '2.5B'
        999 -> '999'
    """
    n = int(n or 0)
    if n >= 1_000_000_000:
        val, suffix = n / 1_000_000_000, "B"
    elif n >= 1_000_000:
        val, suffix = n / 1_000_000, "M"
    elif n >= 1_000:
        val, suffix = n / 1_000, "K"
    else:
        return str(n)
    return f"{val:.2f}".rstrip("0").rstrip(".") + suffix


def format_cost(cost: float) -> str:
    """Format cost value for display.

    Returns '0.00' for zero or negative costs, otherwise formats to 4 decimal places.
    """
    if cost <= 0:
        return "0.00"
    return f"{cost:.4f}"


def get_os_description() -> str:
    system = platform.system() or "Unknown"

    if system == "Darwin":
        ver = platform.mac_ver()[0] or platform.release()
        return f"macOS {ver}".strip()

    if system == "Windows":
        release, version, *_ = platform.win32_ver()
        if release and version:
            return f"Windows {release} ({version})"
        return "Windows"

    if system == "Linux":
        kernel = platform.release()
        return f"Linux (kernel {kernel})" if kernel else "Linux"

    return platform.platform() or system


# Pattern to match OpenHands LLM proxy URLs (e.g., https://llm-proxy.app.all-hands.dev/)
# Must match the host part of the URL, not arbitrary path components
_LLM_PROXY_PATTERN = re.compile(r"^https?://llm-proxy\.[^.]+\.all-hands\.dev(?:/|$)")


def should_set_litellm_extra_body(model_name: str, base_url: str | None = None) -> bool:
    """
    Determine if litellm_extra_body should be set based on the model name or base URL.

    Set litellm_extra_body for:
    - Models with "openhands/" prefix
    - Any model using OpenHands LLM proxy (llm-proxy.*.all-hands.dev)

    This avoids issues with providers that don't support extra_body parameters.

    The SDK internally translates "openhands/" prefix to "litellm_proxy/"
    when making API calls.

    Args:
        model_name: Name of the LLM model
        base_url: Optional base URL for the LLM service

    Returns:
        True if litellm_extra_body should be set, False otherwise
    """
    if "openhands/" in model_name:
        return True

    if base_url and _LLM_PROXY_PATTERN.match(base_url):
        return True

    return False


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
            "app:openhands-cli",
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


def get_default_cli_tools() -> list[Tool]:
    """Get the default tool specifications for CLI mode (browser disabled)."""
    return [
        Tool(name=TerminalTool.name),
        Tool(name=FileEditorTool.name),
        Tool(name=TaskTrackerTool.name),
        Tool(name=DelegateTool.name),
    ]


def get_default_cli_agent(llm: LLM) -> Agent:
    """Create the default CLI agent with all tools (browser disabled)."""
    return Agent(
        llm=llm,
        tools=get_default_cli_tools(),
        system_prompt_kwargs={"cli_mode": True},
        condenser=get_default_condenser(
            llm=llm.model_copy(update={"usage_id": "condenser"})
        ),
    )


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


def extract_text_from_message_content(
    message_content: list[TextContent | ImageContent], has_exactly_one=True
) -> str | None:
    """Extract text from message content for slash command detection.

    Args:
        message_content: Message content (typically a list of content blocks)

    Returns:
        The text content of first TextContent block, None otherwise
    """

    if len(message_content) == 0:
        return None

    if has_exactly_one and len(message_content) != 1:
        return None

    # Only accept single TextContent blocks for slash commands
    if not isinstance(message_content[0], TextContent):
        return None

    # Use SDK utility to extract text - content_to_str handles the conversion
    return message_content[0].text


def json_callback(event: Event) -> None:
    if isinstance(event, SystemPromptEvent):
        return

    data = event.model_dump()
    pretty_json = json.dumps(data, indent=2, sort_keys=True)
    print("--JSON Event--")
    print(pretty_json)
