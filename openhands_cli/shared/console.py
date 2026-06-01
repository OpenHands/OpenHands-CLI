"""Shared console instances for consistent output across the CLI.

This module provides singleton Console instances to avoid creating multiple
Console objects throughout the codebase. Using shared instances improves
performance and ensures consistent output formatting.

Usage:
    from openhands_cli.shared.console import console, stderr_console

    console.print("Hello, world!")
    stderr_console.print("Error message", style="red")
"""

from rich.console import Console


# Standard console for normal output (highlight disabled, soft wrap enabled)
console: Console = Console(highlight=False, soft_wrap=True)

# Console for stderr output
stderr_console: Console = Console(stderr=True, highlight=False, soft_wrap=True)
