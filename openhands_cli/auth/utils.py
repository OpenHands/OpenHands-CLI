"""Utility functions for auth module."""

from rich.console import Console


# Create a console instance for printing
_console = Console()


def _p(message: str) -> None:
    """Unified formatted print helper using rich console."""
    _console.print(message)
