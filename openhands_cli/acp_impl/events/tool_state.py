import json

from acp.schema import ToolKind
from streamingjson import Lexer

from openhands_cli.acp_impl.events.shared_event_handler import THOUGHT_HEADER
from openhands_cli.acp_impl.events.utils import TOOL_KIND_MAPPING


class ToolCallState:
    """Manages the state of a single streaming tool call.

    Uses Lexer to incrementally parse JSON arguments
    and extract key arguments for dynamic titles.

    The `kind` and `title` properties are only valid after `has_valid_skeleton`
    returns True. Accessing them before raises ValueError.
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
        self._valid_skeleton_cached = False
        # Kind is cached once skeleton is valid (depends only on command, not path)
        self._cached_kind: ToolKind | None = None

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
    def kind(self) -> ToolKind:
        """Get the tool kind based on tool name and parsed args.

        Raises:
            ValueError: If has_valid_skeleton is False.
        """
        if not self.has_valid_skeleton:
            raise ValueError(
                f"Cannot access kind before has_valid_skeleton is True "
                f"(tool={self.tool_name}, args={self.args!r})"
            )

        if self._cached_kind is not None:
            return self._cached_kind

        kind = self._compute_kind()
        self._cached_kind = kind
        return kind

    def _compute_kind(self) -> ToolKind:
        """Compute kind from tool name and args."""
        if self.tool_name == "think":
            return "think"

        if self.tool_name.startswith("browser"):
            return "fetch"

        if self.tool_name == "file_editor":
            args = self._parse_args()
            command = args.get("command", "") if args else ""
            # Prefix match: streaming may yield "v", "vi", etc. before full "view"
            if isinstance(command, str) and command and "view".startswith(command):
                return "read"
            return "edit"

        return TOOL_KIND_MAPPING.get(self.tool_name, "other")

    @property
    def title(self) -> str:
        """Get the current title based on tool name and parsed args.

        Note: Title is not cached since args (e.g., path) may arrive after
        the skeleton becomes valid.

        Raises:
            ValueError: If has_valid_skeleton is False.
        """
        if not self.has_valid_skeleton:
            raise ValueError(
                f"Cannot access title before has_valid_skeleton is True "
                f"(tool={self.tool_name}, args={self.args!r})"
            )
        return self._compute_title()

    def _compute_title(self) -> str:
        """Compute title from tool name and args."""
        if self.tool_name == "task_tracker":
            return "Plan updated"

        args = self._parse_args()
        if not args:
            return self.tool_name

        if self.tool_name == "file_editor":
            path = args.get("path")
            command = args.get("command")
            if isinstance(path, str) and path:
                # Prefix match: streaming may yield "v", "vi", etc. before full "view"
                if isinstance(command, str) and "view".startswith(command):
                    return f"Reading {path}"
                return f"Editing {path}"

        if self.tool_name == "terminal":
            command = args.get("command")
            if isinstance(command, str) and command:
                return command

        return self.tool_name

    def _parse_args(self) -> dict | None:
        """Parse current args using lexer's best-effort completion."""
        try:
            args = json.loads(self.lexer.complete_json())
            return args if isinstance(args, dict) else None
        except Exception:
            return None

    @property
    def has_valid_skeleton(self) -> bool:
        """Check if we have enough args to consider this a valid tool call.

        This prevents flickering from noisy models that emit a tool name
        then hesitate or abandon the call. We delay starting until args
        contain at least one key with any non-null value.

        For tools where kind depends on specific args (e.g., file_editor needs
        'command' to distinguish read vs edit), we wait until that arg is present.
        This prevents kind churn during streaming.

        Result is cached once True since args only accumulate.
        """
        if self._valid_skeleton_cached:
            return True

        if not self.args:
            return False

        parsed = self._parse_args()
        if not parsed:
            return False

        # Valid if any key has a non-null value with actual content
        has_any_content = any(
            v is not None and (not isinstance(v, str) or v) for v in parsed.values()
        )
        if not has_any_content:
            return False

        # For file_editor, require 'command' to be present to determine kind correctly
        if self.tool_name == "file_editor":
            command = parsed.get("command")
            if not isinstance(command, str) or not command:
                return False

        self._valid_skeleton_cached = True
        return True

    def __repr__(self) -> str:
        # Avoid ValueError by checking skeleton first
        title_repr = (
            repr(self._compute_title()) if self._valid_skeleton_cached else "N/A"
        )
        return (
            f"ToolCallState(\n"
            f"  id={self.tool_call_id!r},\n"
            f"  tool={self.tool_name!r},\n"
            f"  title={title_repr},\n"
            f"  is_think={self.is_think},\n"
            f"  is_started={self.started},\n"
            f"  has_valid_skeleton={self._valid_skeleton_cached},\n"
            f"  args={self.args!r}\n"
            f")"
        )
