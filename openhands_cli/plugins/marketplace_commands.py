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
        marketplace = storage.add_marketplace(url=args.url, name=name)
        console.print(
            f"Successfully added marketplace: {args.url}",
            style=OPENHANDS_THEME.success,
        )
        if marketplace.name:
            console.print(f"  Name: {marketplace.name}", style=OPENHANDS_THEME.secondary)
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
        storage.remove_marketplace(url=args.url)
        console.print(
            f"Successfully removed marketplace: {args.url}",
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
                "No plugin marketplaces configured", style=OPENHANDS_THEME.warning
            )
            console.print(
                "Use [bold]openhands plugin marketplace add <url>[/bold] "
                "to add a marketplace",
                style=OPENHANDS_THEME.accent,
            )
            return

        # Create a table for display
        table = Table(title="Configured Plugin Marketplaces")
        table.add_column("URL", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Added", style="dim")
        table.add_column("Last Updated", style="dim")

        for m in marketplaces:
            # Format timestamps for display
            added = m.added_at[:10] if m.added_at else "-"
            updated = m.last_updated[:10] if m.last_updated else "-"

            table.add_row(
                m.url,
                m.name or "-",
                added,
                updated,
            )

        console.print(table)

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
                "No plugin marketplaces configured", style=OPENHANDS_THEME.warning
            )
            return

        # Filter by URL if specified
        url_filter = getattr(args, "url", None)
        if url_filter:
            marketplaces = [m for m in marketplaces if m.url == url_filter]
            if not marketplaces:
                console.print(
                    f"Marketplace not found: {url_filter}",
                    style=OPENHANDS_THEME.error,
                )
                raise SystemExit(1)

        # Update each marketplace
        for marketplace in marketplaces:
            console.print(
                f"Updating marketplace: {marketplace.url}",
                style=OPENHANDS_THEME.foreground,
            )
            # For now, just update the timestamp
            # In the future, this would fetch and cache the marketplace index
            storage.update_marketplace_timestamp(marketplace.url)
            console.print(
                f"  Updated: {marketplace.url}",
                style=OPENHANDS_THEME.success,
            )

        console.print(
            f"Successfully updated {len(marketplaces)} marketplace(s)",
            style=OPENHANDS_THEME.success,
        )

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
