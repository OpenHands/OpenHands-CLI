"""Plugin management command handlers for the CLI interface.

This module provides command handlers for managing installed plugins
through the command line interface.
"""

import argparse
from datetime import datetime

from rich.console import Console
from rich.table import Table

from openhands_cli.plugins.marketplace_storage import MarketplaceStorage
from openhands_cli.plugins.plugin_storage import (
    InstalledPlugin,
    PluginStorage,
    PluginStorageError,
)
from openhands_cli.theme import OPENHANDS_THEME


console = Console()


def _format_time_ago(iso_timestamp: str) -> str:
    """Format an ISO timestamp as a relative time string.

    Args:
        iso_timestamp: ISO format timestamp string.

    Returns:
        Human-readable relative time (e.g., "2 days ago").
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        delta = now - dt

        if delta.days == 0:
            if delta.seconds < 60:
                return "just now"
            elif delta.seconds < 3600:
                mins = delta.seconds // 60
                return f"{mins} minute{'s' if mins != 1 else ''} ago"
            else:
                hours = delta.seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.days == 1:
            return "1 day ago"
        elif delta.days < 30:
            return f"{delta.days} days ago"
        elif delta.days < 365:
            months = delta.days // 30
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = delta.days // 365
            return f"{years} year{'s' if years != 1 else ''} ago"
    except (ValueError, TypeError):
        return iso_timestamp[:10] if iso_timestamp else "-"


def handle_plugin_install(args: argparse.Namespace) -> None:
    """Handle the 'plugin install' command.

    Args:
        args: Parsed command line arguments
    """
    storage = PluginStorage()
    marketplace_storage = MarketplaceStorage()

    try:
        plugin_spec = args.plugin

        # Parse plugin specification (name@marketplace or just name)
        if "@" in plugin_spec:
            name, marketplace = plugin_spec.rsplit("@", 1)
        else:
            # If no marketplace specified, check if there's only one configured
            marketplaces = marketplace_storage.list_marketplaces()
            if not marketplaces:
                console.print(
                    "No marketplaces configured. Add a marketplace first:",
                    style=OPENHANDS_THEME.error,
                )
                console.print(
                    "  openhands plugin marketplace add <url>",
                    style=OPENHANDS_THEME.secondary,
                )
                raise SystemExit(1)
            elif len(marketplaces) == 1:
                marketplace = marketplaces[0].name or marketplaces[0].url
                name = plugin_spec
            else:
                console.print(
                    f"Multiple marketplaces configured. Please specify marketplace:",
                    style=OPENHANDS_THEME.error,
                )
                console.print(
                    f"  openhands plugin install {plugin_spec}@<marketplace>",
                    style=OPENHANDS_THEME.secondary,
                )
                raise SystemExit(1)

        console.print(
            f"Installing '{name}' from {marketplace}...",
            style=OPENHANDS_THEME.foreground,
        )

        # Get version if specified
        version = getattr(args, "version", None)

        # Install the plugin
        plugin = storage.install_plugin(
            name=name,
            marketplace=marketplace,
            version=version,
        )

        console.print()
        console.print(
            f"Plugin '{plugin.full_name}' installed!",
            style=OPENHANDS_THEME.success,
        )
        if plugin.version:
            console.print(f"  Version: {plugin.version}", style=OPENHANDS_THEME.secondary)
        console.print()
        console.print(
            "The plugin is enabled and will be loaded in new conversations.",
            style=OPENHANDS_THEME.accent,
        )

    except PluginStorageError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_plugin_uninstall(args: argparse.Namespace) -> None:
    """Handle the 'plugin uninstall' command.

    Args:
        args: Parsed command line arguments
    """
    storage = PluginStorage()

    try:
        # Resolve plugin name to full name
        full_name = storage.resolve_plugin_name(args.plugin)

        storage.uninstall_plugin(full_name)
        console.print(
            f"Successfully uninstalled plugin: {full_name}",
            style=OPENHANDS_THEME.success,
        )

    except PluginStorageError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_plugin_list(args: argparse.Namespace) -> None:
    """Handle the 'plugin list' command.

    Args:
        args: Parsed command line arguments
    """
    storage = PluginStorage()

    try:
        enabled_only = getattr(args, "enabled", False)
        disabled_only = getattr(args, "disabled", False)

        plugins = storage.list_plugins(
            enabled_only=enabled_only,
            disabled_only=disabled_only,
        )

        if not plugins:
            if enabled_only:
                console.print("No enabled plugins", style=OPENHANDS_THEME.warning)
            elif disabled_only:
                console.print("No disabled plugins", style=OPENHANDS_THEME.warning)
            else:
                console.print("No plugins installed", style=OPENHANDS_THEME.warning)
            console.print(
                "Use [bold]openhands plugin install <name>@<marketplace>[/bold] "
                "to install a plugin",
                style=OPENHANDS_THEME.accent,
            )
            return

        console.print("Installed plugins:", style=OPENHANDS_THEME.foreground)
        console.print()

        for plugin in plugins:
            _render_plugin_summary(plugin)
            console.print()

        # Summary
        enabled_count = sum(1 for p in plugins if p.enabled)
        disabled_count = len(plugins) - enabled_count
        console.print(
            f"{len(plugins)} plugin(s) installed "
            f"({enabled_count} enabled, {disabled_count} disabled)",
            style=OPENHANDS_THEME.secondary,
        )

    except PluginStorageError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def _render_plugin_summary(plugin: InstalledPlugin) -> None:
    """Render a plugin summary for list view.

    Args:
        plugin: The plugin to render.
    """
    status = "[enabled]" if plugin.enabled else "[disabled]"
    status_style = OPENHANDS_THEME.success if plugin.enabled else OPENHANDS_THEME.warning

    version_str = f" (v{plugin.version})" if plugin.version else ""

    console.print(
        f"  {plugin.full_name}{version_str} ",
        style=OPENHANDS_THEME.accent,
        end="",
    )
    console.print(status, style=status_style)

    # Show installed time
    installed_ago = _format_time_ago(plugin.installed_at)
    console.print(f"    Installed: {installed_ago}", style=OPENHANDS_THEME.secondary)


def handle_plugin_enable(args: argparse.Namespace) -> None:
    """Handle the 'plugin enable' command.

    Args:
        args: Parsed command line arguments
    """
    storage = PluginStorage()

    try:
        full_name = storage.resolve_plugin_name(args.plugin)
        storage.enable_plugin(full_name)
        console.print(
            f"Successfully enabled plugin: {full_name}",
            style=OPENHANDS_THEME.success,
        )
        console.print(
            "The plugin will be loaded in new conversations.",
            style=OPENHANDS_THEME.accent,
        )

    except PluginStorageError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_plugin_disable(args: argparse.Namespace) -> None:
    """Handle the 'plugin disable' command.

    Args:
        args: Parsed command line arguments
    """
    storage = PluginStorage()

    try:
        full_name = storage.resolve_plugin_name(args.plugin)
        storage.disable_plugin(full_name)
        console.print(
            f"Successfully disabled plugin: {full_name}",
            style=OPENHANDS_THEME.success,
        )
        console.print(
            "The plugin will not be loaded in new conversations.",
            style=OPENHANDS_THEME.accent,
        )

    except PluginStorageError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_plugin_info(args: argparse.Namespace) -> None:
    """Handle the 'plugin info' command.

    Args:
        args: Parsed command line arguments
    """
    storage = PluginStorage()

    try:
        full_name = storage.resolve_plugin_name(args.plugin)
        plugin = storage.get_plugin(full_name)

        if not plugin:
            console.print(f"Plugin not found: {full_name}", style=OPENHANDS_THEME.error)
            raise SystemExit(1)

        # Display plugin info
        console.print(f"Plugin: {plugin.name}", style=OPENHANDS_THEME.accent)
        console.print(f"Marketplace: {plugin.marketplace}", style=OPENHANDS_THEME.foreground)

        if plugin.version:
            console.print(f"Version: {plugin.version}", style=OPENHANDS_THEME.foreground)

        status = "enabled" if plugin.enabled else "disabled"
        status_style = OPENHANDS_THEME.success if plugin.enabled else OPENHANDS_THEME.warning
        console.print(f"Status: ", style=OPENHANDS_THEME.foreground, end="")
        console.print(status, style=status_style)

        console.print(f"Installed: {plugin.installed_at}", style=OPENHANDS_THEME.secondary)

        if plugin.source_url:
            console.print(f"Source: {plugin.source_url}", style=OPENHANDS_THEME.secondary)

        if plugin.resolved_ref:
            console.print(f"Ref: {plugin.resolved_ref}", style=OPENHANDS_THEME.secondary)

    except PluginStorageError as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)


def handle_plugin_search(args: argparse.Namespace) -> None:
    """Handle the 'plugin search' command.

    Args:
        args: Parsed command line arguments
    """
    marketplace_storage = MarketplaceStorage()

    try:
        query = args.query
        marketplace_filter = getattr(args, "marketplace", None)

        marketplaces = marketplace_storage.list_marketplaces()

        if not marketplaces:
            console.print(
                "No marketplaces configured. Add a marketplace first:",
                style=OPENHANDS_THEME.warning,
            )
            console.print(
                "  openhands plugin marketplace add <url>",
                style=OPENHANDS_THEME.secondary,
            )
            return

        if marketplace_filter:
            marketplaces = [
                m for m in marketplaces
                if m.name == marketplace_filter or m.url == marketplace_filter
            ]
            if not marketplaces:
                console.print(
                    f"Marketplace not found: {marketplace_filter}",
                    style=OPENHANDS_THEME.error,
                )
                raise SystemExit(1)

        console.print("Searching marketplaces...", style=OPENHANDS_THEME.foreground)
        console.print()

        # Note: In a full implementation, this would fetch and search marketplace indexes
        # For now, we just show a placeholder message
        console.print(
            f"Search for '{query}' across {len(marketplaces)} marketplace(s)",
            style=OPENHANDS_THEME.secondary,
        )
        console.print()
        console.print(
            "Note: Marketplace search requires marketplace indexes to be implemented.",
            style=OPENHANDS_THEME.warning,
        )
        console.print(
            "For now, use 'openhands plugin install <name>@<marketplace>' directly.",
            style=OPENHANDS_THEME.accent,
        )

    except Exception as e:
        console.print(f"Error: {e}", style=OPENHANDS_THEME.error)
        raise SystemExit(1)
