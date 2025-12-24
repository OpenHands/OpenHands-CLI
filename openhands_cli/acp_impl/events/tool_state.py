import json

from streamingjson import Lexer

from openhands_cli.acp_impl.events.shared_event_handler import THOUGHT_HEADER
from openhands_cli.acp_impl.events.utils import get_tool_title


class ToolCallState:
    """Manages the state of a single streaming tool call.

    Uses Lexer to incrementally parse JSON arguments
    and extract key arguments for dynamic titles.
    """

    def __init__(self, tool_call_id: str, tool_name: str):
        self.tool_call_id = tool_call_id
        self.tool_name = tool_name
        self.is_think = tool_name == "think"
        self.args = ""
        self.lexer = Lexer()
        self.prev_emitted_thought_chunk = ""
        self.started = False
        self.thought_header_emitted = False

    def append_args(self, args_part: str) -> None:
        """Append new arguments part to the accumulated args and lexer."""
        self.args += args_part
        self.lexer.append_string(args_part)

    def extract_thought_piece(self) -> str | None:
        """Incrementally emit new text from the Think tool's `thought` argument.

        Reparses the best-effort JSON args and diffs against the previously
        emitted prefix. Prepends THOUGHT_HEADER on the first non-empty delta
        for consistent formatting with non-streaming mode.
        """
        if not self.is_think:
            return None

        try:
            args = json.loads(self.lexer.complete_json())
        except Exception:
            return None

        thought = args.get("thought", "")
        if not thought:
            return None

        prev = self.prev_emitted_thought_chunk
        delta = thought[len(prev) :]
        if not delta:
            return None

        self.prev_emitted_thought_chunk = thought

        # Prepend header on first thought piece for consistency
        # with non-streaming mode (EventSubscriber)
        if not self.thought_header_emitted:
            self.thought_header_emitted = True
            delta = THOUGHT_HEADER + delta

        return delta

    @property
    def title(self) -> str:
        """Get the current title with key argument if available."""
        return get_tool_title(tool_name=self.tool_name, partial_args=self.lexer)

    def __repr__(self) -> str:
        return (
            f"ToolCallState(\n"
            f"  id={self.tool_call_id!r},\n"
            f"  tool={self.tool_name!r},\n"
            f"  title={self.title!r},\n"
            f"  is_think={self.is_think},\n"
            f"  is_started={self.started},\n"
            f"  args={self.args!r}\n"
            f")"
        )
