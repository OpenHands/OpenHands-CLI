import json

import streamingjson


def _shorten_middle(text: str, width: int = 50) -> str:
    """Shorten a string by removing the middle part if it exceeds the width."""
    if len(text) <= width:
        return text
    half = (width - 3) // 2
    return text[:half] + "..." + text[-half:]


def _extract_key_argument(lexer: streamingjson.Lexer, tool_name: str) -> str | None:
    """Extract a key argument from tool call arguments for display.

    Uses streamingjson.Lexer to handle incomplete JSON and extracts
    the most relevant argument based on the tool name.
    """
    try:
        curr_args = json.loads(lexer.complete_json())
    except json.JSONDecodeError:
        return None

    if not curr_args or not isinstance(curr_args, dict):
        return None

    key_argument: str | None = None

    # Map tool names to their key arguments
    if tool_name == "terminal":
        key_argument = curr_args.get("command")
    elif tool_name == "file_editor":
        key_argument = curr_args.get("path")
    elif tool_name == "think":
        key_argument = curr_args.get("thought")
    elif tool_name == "finish":
        key_argument = curr_args.get("message")
    elif tool_name == "task_tracker":
        return None
    elif tool_name.startswith("browser"):
        key_argument = (
            curr_args.get("url")
            or (f"index={curr_args['index']}" if curr_args.get("index") else None)
            or curr_args.get("text")
        )
    else:
        # For unknown tools, try common argument names
        for key in ["path", "command", "query", "url", "text", "message"]:
            if curr_args.get(key):
                key_argument = curr_args[key]
                break

    if key_argument:
        return _shorten_middle(str(key_argument), width=50)
    return None


class ToolCallState:
    """Manages the state of a single streaming tool call.

    Uses streamingjson.Lexer to incrementally parse JSON arguments
    and extract key arguments for dynamic titles.
    """

    def __init__(self, tool_call_id: str, tool_name: str, is_think: bool = False):
        self.tool_call_id = tool_call_id
        self.tool_name = tool_name
        self.is_think = is_think
        self.args = ""
        self.lexer = streamingjson.Lexer()
        self.started = False

    def append_args(self, args_part: str) -> None:
        """Append new arguments part to the accumulated args and lexer."""
        self.args += args_part
        self.lexer.append_string(args_part)

    @property
    def title(self) -> str:
        """Get the current title with key argument if available."""
        subtitle = _extract_key_argument(self.lexer, self.tool_name)
        if subtitle:
            return f"{self.tool_name}: {subtitle}"
        return self.tool_name
