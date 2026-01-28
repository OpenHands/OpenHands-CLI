"""Marketplace command handlers for the CLI interface.

This module provides command handlers for managing plugin marketplace configurations
through the command line interface.
"""

import argparse

from rich.console import Console
from rich.table import Table

from openhands_cli.plugins.marketplace_storage import (
    MarketplaceError,
    MarketplaceStorage,
)
from openhands_cli.theme import OPENHANDS_THEME


console = Console()


def handle_marketplace_add(args: argparse.Namespace) -> None:
    """Handle the 'plugin marketplace add' command.

    Args:
        args: Parsed command line arguments
    """
    storage = MarketplaceStorage()
    try:
        name = getattr(args, "name", None)
        marketplace = storage.add_marketplace(source_str=args.source, name=name)
        console.print(
            f"Added marketplace '{marketplace.name}'",
            style=OPENHANDS_THEME.success,
        )
        console.print(f"  Source: {marketplace.source}", style=OPENHANDS_THEME.secondary)
    except MarketplaceError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_marketplace_remove(args: argparse.Namespace) -> None:
    """Handle the 'plugin marketplace remove' command.

    Args:
        args: Parsed command line arguments
    """
    storage = MarketplaceStorage()
    try:
        storage.remove_marketplace(name=args.name)
        console.print(
            f"Removed marketplace '{args.name}'",
            style=OPENHANDS_THEME.success,
        )
    except MarketplaceError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_marketplace_list(_args: argparse.Namespace) -> None:
    """Handle the 'plugin marketplace list' command.

    Args:
        _args: Parsed command line arguments (unused)
    """
    storage = MarketplaceStorage()
    try:
        marketplaces = storage.list_marketplaces()

        if not marketplaces:
            console.print(
                "No plugin marketplaces configured.", style=OPENHANDS_THEME.warning
            )
            console.print(
                "Use [bold]openhands plugin marketplace add <source>[/bold] "
                "to add a marketplace.",
                style=OPENHANDS_THEME.accent,
            )
            return

        # Create a table for display
        table = Table(title="Configured Plugin Marketplaces")
        table.add_column("Name", style="green", no_wrap=True)
        table.add_column("Source", style="cyan")
        table.add_column("Plugins", style="magenta", justify="right")
        table.add_column("Auto Update", style="dim")
        table.add_column("Added", style="dim")
        table.add_column("Last Updated", style="dim")

        total_plugins = 0

        for m in marketplaces:
            # Format timestamps for display
            added = m.added_at[:10] if m.added_at else "-"
            updated = m.last_updated[:10] if m.last_updated else "-"
            auto_update = "Yes" if m.auto_update else "No"

            # Get plugin count from cached index
            cached_index = storage.get_cached_index(m.name)
            if cached_index:
                plugin_count = len(cached_index.get("plugins", []))
                total_plugins += plugin_count
                plugins_str = str(plugin_count)
            else:
                plugins_str = "-"

            table.add_row(
                m.name,
                str(m.source),
                plugins_str,
                auto_update,
                added,
                updated,
            )

        console.print(table)
        console.print(
            f"\n{len(marketplaces)} marketplace(s) configured. "
            f"Plugins available: {total_plugins}",
            style=OPENHANDS_THEME.secondary,
        )

    except MarketplaceError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_marketplace_update(args: argparse.Namespace) -> None:
    """Handle the 'plugin marketplace update' command.

    Args:
        args: Parsed command line arguments
    """
    storage = MarketplaceStorage()
    try:
        marketplaces = storage.list_marketplaces()

        if not marketplaces:
            console.print(
                "No plugin marketplaces configured.", style=OPENHANDS_THEME.warning
            )
            return

        # Filter by name if specified
        name_filter = getattr(args, "name", None)
        if name_filter:
            marketplaces = [m for m in marketplaces if m.name == name_filter]
            if not marketplaces:
                console.print(
                    f"Marketplace not found: {name_filter}",
                    style=OPENHANDS_THEME.error,
                )
                raise SystemExit(1)

        # Update each marketplace
        updated_count = 0
        failed_count = 0
        for marketplace in marketplaces:
            console.print(
                f"Updating marketplace '{marketplace.name}'...",
                style=OPENHANDS_THEME.foreground,
            )
            try:
                # Fetch and cache the marketplace index
                index_data = storage.update_marketplace(marketplace.name)
                plugin_count = len(index_data.get("plugins", []))
                console.print(
                    f"  Updated: {marketplace.name} ({plugin_count} plugins)",
                    style=OPENHANDS_THEME.success,
                )
                updated_count += 1
            except MarketplaceError as e:
                console.print(
                    f"  Failed: {e}",
                    style=OPENHANDS_THEME.error,
                )
                failed_count += 1

        if updated_count > 0:
            console.print(
                f"Successfully updated {updated_count} marketplace(s).",
                style=OPENHANDS_THEME.success,
            )
        if failed_count > 0:
            console.print(
                f"Failed to update {failed_count} marketplace(s).",
                style=OPENHANDS_THEME.warning,
            )
            if updated_count == 0:
                raise SystemExit(1)

    except MarketplaceError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_marketplace_command(args: argparse.Namespace) -> None:
    """Main handler for marketplace subcommands.

    Args:
        args: Parsed command line arguments
    """
    marketplace_cmd = getattr(args, "marketplace_command", None)

    if marketplace_cmd == "add":
        handle_marketplace_add(args)
    elif marketplace_cmd == "remove":
        handle_marketplace_remove(args)
    elif marketplace_cmd == "list":
        handle_marketplace_list(args)
    elif marketplace_cmd == "update":
        handle_marketplace_update(args)
    else:
        console.print(
            "Unknown marketplace command. Use --help for usage.",
            style=OPENHANDS_THEME.error,
        )
        raise SystemExit(1)


def handle_plugin_command(args: argparse.Namespace) -> None:
    """Main handler for plugin commands.

    Args:
        args: Parsed command line arguments
    """
    from openhands_cli.plugins.plugin_commands import (
        handle_plugin_disable,
        handle_plugin_enable,
        handle_plugin_info,
        handle_plugin_install,
        handle_plugin_list,
        handle_plugin_search,
        handle_plugin_uninstall,
    )

    plugin_cmd = getattr(args, "plugin_command", None)

    if plugin_cmd == "marketplace":
        handle_marketplace_command(args)
    elif plugin_cmd == "install":
        handle_plugin_install(args)
    elif plugin_cmd == "uninstall":
        handle_plugin_uninstall(args)
    elif plugin_cmd == "list":
        handle_plugin_list(args)
    elif plugin_cmd == "enable":
        handle_plugin_enable(args)
    elif plugin_cmd == "disable":
        handle_plugin_disable(args)
    elif plugin_cmd == "info":
        handle_plugin_info(args)
    elif plugin_cmd == "search":
        handle_plugin_search(args)
    else:
        console.print(
            "Unknown plugin command. Use --help for usage.",
            style=OPENHANDS_THEME.error,
        )
        raise SystemExit(1)
