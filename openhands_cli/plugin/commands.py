"""Plugin command handlers for OpenHands CLI."""

from __future__ import annotations

import json
import sys
from argparse import Namespace

from rich.console import Console
from rich.table import Table

from openhands_cli.theme import OPENHANDS_THEME


console = Console()


def handle_plugin_command(args: Namespace) -> None:
    """Handle plugin subcommand.

    Args:
        args: Parsed command line arguments
    """
    if args.plugin_command is None:
        # No subcommand specified, show help
        console.print(
            "Usage: openhands plugin <command> [options]",
            style=OPENHANDS_THEME.secondary,
        )
        console.print("\nCommands:")
        console.print("  list       List installed plugins")
        console.print("  install    Install a plugin from a source")
        console.print("  uninstall  Uninstall a plugin")
        console.print("  update     Update an installed plugin")
        console.print("\nRun 'openhands plugin <command> --help' for more information.")
        return

    match args.plugin_command:
        case "list":
            _handle_list(args)
        case "install":
            _handle_install(args)
        case "uninstall":
            _handle_uninstall(args)
        case "update":
            _handle_update(args)


def _handle_list(args: Namespace) -> None:
    """Handle 'plugin list' command."""
    from openhands.sdk.plugin import (
        get_installed_plugins_dir,
        list_installed_plugins,
    )

    try:
        plugins = list_installed_plugins()
        plugins_dir = get_installed_plugins_dir()

        if args.json:
            # JSON output
            output = {
                "plugins_dir": str(plugins_dir),
                "plugins": [p.model_dump() for p in plugins],
            }
            print(json.dumps(output, indent=2))
            return

        # Rich table output
        if not plugins:
            console.print(
                f"No plugins installed in {plugins_dir}",
                style=OPENHANDS_THEME.secondary,
            )
            return

        console.print(
            f"\n[bold {OPENHANDS_THEME.primary}]Installed Plugins[/bold {OPENHANDS_THEME.primary}]"
        )
        console.print(f"[dim]Location: {plugins_dir}[/dim]\n")

        table = Table(show_header=True, header_style=OPENHANDS_THEME.primary)
        table.add_column("Name", style=OPENHANDS_THEME.secondary)
        table.add_column("Version")
        table.add_column("Description")
        table.add_column("Source", style="dim")

        for plugin in plugins:
            source_display = plugin.source
            if plugin.resolved_ref:
                source_display += f" ({plugin.resolved_ref[:8]})"
            table.add_row(
                plugin.name,
                plugin.version,
                plugin.description or "",
                source_display,
            )

        console.print(table)

    except Exception as e:
        console.print(f"Error listing plugins: {e}", style=OPENHANDS_THEME.error)
        sys.exit(1)


def _handle_install(args: Namespace) -> None:
    """Handle 'plugin install' command."""
    from openhands.sdk.plugin import PluginFetchError, install_plugin

    source = args.source
    ref = args.ref
    repo_path = args.repo_path
    force = args.force

    console.print(
        f"Installing plugin from {source}...",
        style=OPENHANDS_THEME.secondary,
    )

    try:
        info = install_plugin(
            source=source,
            ref=ref,
            repo_path=repo_path,
            force=force,
        )

        console.print(
            f"\n[bold {OPENHANDS_THEME.success}]✓ Successfully installed "
            f"'{info.name}' v{info.version}[/bold {OPENHANDS_THEME.success}]"
        )
        if info.description:
            console.print(f"  {info.description}", style="dim")
        console.print(f"  Source: {info.source}", style="dim")
        if info.resolved_ref:
            console.print(f"  Ref: {info.resolved_ref[:8]}", style="dim")
        console.print(f"  Installed to: {info.install_path}", style="dim")

    except FileExistsError as e:
        console.print(f"\n{e}", style=OPENHANDS_THEME.warning)
        console.print(
            "Use --force to overwrite the existing installation.",
            style=OPENHANDS_THEME.secondary,
        )
        sys.exit(1)
    except PluginFetchError as e:
        console.print(f"\nFailed to fetch plugin: {e}", style=OPENHANDS_THEME.error)
        sys.exit(1)
    except Exception as e:
        console.print(f"\nError installing plugin: {e}", style=OPENHANDS_THEME.error)
        sys.exit(1)


def _handle_uninstall(args: Namespace) -> None:
    """Handle 'plugin uninstall' command."""
    from openhands.sdk.plugin import uninstall_plugin

    name = args.name

    console.print(
        f"Uninstalling plugin '{name}'...",
        style=OPENHANDS_THEME.secondary,
    )

    try:
        success = uninstall_plugin(name)

        if success:
            console.print(
                f"\n[bold {OPENHANDS_THEME.success}]✓ Successfully uninstalled "
                f"'{name}'[/bold {OPENHANDS_THEME.success}]"
            )
        else:
            console.print(
                f"\nPlugin '{name}' is not installed.",
                style=OPENHANDS_THEME.warning,
            )
            sys.exit(1)

    except Exception as e:
        console.print(f"\nError uninstalling plugin: {e}", style=OPENHANDS_THEME.error)
        sys.exit(1)


def _handle_update(args: Namespace) -> None:
    """Handle 'plugin update' command."""
    from openhands.sdk.plugin import PluginFetchError, update_plugin

    name = args.name

    console.print(
        f"Updating plugin '{name}'...",
        style=OPENHANDS_THEME.secondary,
    )

    try:
        info = update_plugin(name)

        if info is None:
            console.print(
                f"\nPlugin '{name}' is not installed.",
                style=OPENHANDS_THEME.warning,
            )
            sys.exit(1)

        console.print(
            f"\n[bold {OPENHANDS_THEME.success}]✓ Successfully updated "
            f"'{info.name}' to v{info.version}[/bold {OPENHANDS_THEME.success}]"
        )
        if info.resolved_ref:
            console.print(f"  New ref: {info.resolved_ref[:8]}", style="dim")

    except PluginFetchError as e:
        console.print(f"\nFailed to fetch plugin update: {e}", style=OPENHANDS_THEME.error)
        sys.exit(1)
    except Exception as e:
        console.print(f"\nError updating plugin: {e}", style=OPENHANDS_THEME.error)
        sys.exit(1)
