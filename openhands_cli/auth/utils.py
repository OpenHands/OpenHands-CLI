"""Utility functions for auth module."""

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML


def _p(message: str) -> None:
    """Unified formatted print helper."""
    print_formatted_text(HTML(message))