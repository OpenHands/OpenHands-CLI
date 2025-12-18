# Minimal replacement for removed TUI components
from prompt_toolkit.completion import Completer


# Default style placeholder
DEFAULT_STYLE = None


class CommandCompleter(Completer):
    """Minimal command completer placeholder."""

    def get_completions(self, document, complete_event):  # noqa: ARG002
        return []
