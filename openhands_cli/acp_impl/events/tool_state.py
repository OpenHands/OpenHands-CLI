import json

import streamingjson


def _title_from_streaming_args(tool_name: str, lexer: streamingjson.Lexer) -> str:
    """
    Streaming equivalent of _handle_action_event's title logic.

    _handle_action_event titles:
      - file_editor: "Reading {path}" if command == "view" else "Editing {path}"
      - terminal: "{command}"
      - task_tracker: "Plan updated"
      - everything else: tool_name
    """
    if tool_name == "task_tracker":
        return "Plan updated"

    # Best-effort parse of the (possibly incomplete) JSON args
    try:
        args = json.loads(lexer.complete_json())
    except Exception:
        return ""

    if not isinstance(args, dict):
        return tool_name

    if tool_name == "file_editor":
        path = args.get("path")
        command = args.get("command")
        if isinstance(path, str) and path:
            if command == "view":
                return f"Reading {path}"
            return f"Editing {path}"
        return tool_name

    if tool_name == "terminal":
        command = args.get("command")
        # Match _handle_action_event which sets title to event.action.command
        # (for terminal this is usually the shell command string)
        if isinstance(command, str) and command:
            return command
        return tool_name

    # browser/browser_use/etc: _handle_action_event keeps title == tool_name
    return tool_name


class ToolCallState:
    """Manages the state of a single streaming tool call.

    Uses streamingjson.Lexer to incrementally parse JSON arguments
    and extract key arguments for dynamic titles.
    """

    def __init__(self, tool_call_id: str, tool_name: str):
        self.tool_call_id = tool_call_id
        self.tool_name = tool_name
        self.is_think = tool_name == "think"
        self.args = ""
        self.lexer = streamingjson.Lexer()
        self.prev_emitted_thought_chunk = ""
        self.started = False

    def append_args(self, args_part: str) -> None:
        """Append new arguments part to the accumulated args and lexer."""
        self.args += args_part
        self.lexer.append_string(args_part)

    def extract_thought_piece(self, arguments: str) -> str | None:
        """
        Incrementally emit new text from the Think tool's `thought` argument by
        reparsing the best-effort JSON args and diffing against the previously
        emitted prefix.
        """

        if not self.is_think or not arguments:
            return None

        try:
            args = json.loads(self.lexer.complete_json())
        except Exception:
            return None

        thought = args.get("thought", "")
        if not thought:
            return None

        self.prev_emitted_thought_chunk = thought
        return thought[len(self.prev_emitted_thought_chunk) :]

    @property
    def title(self) -> str:
        """Get the current title with key argument if available."""
        return _title_from_streaming_args(self.tool_name, self.lexer)

    def __repr__(self) -> str:
        return (
            f"ToolCallState(\n"
            f"  id={self.tool_call_id!r},\n"
            f"  tool={self.tool_name!r},\n"
            f"  title={self.title!r},\n"
            f"  is_think={self.is_think},\n"
            f". is_started={self.started},\n"
            f"  args={self.args!r}\n"
            f")"
        )
