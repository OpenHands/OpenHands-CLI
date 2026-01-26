"""Argument parser for plugin subcommand."""

import argparse
import sys
from typing import NoReturn


class PluginArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser for plugin commands that shows full help on errors."""

    def error(self, message: str) -> NoReturn:
        """Override error method to show full help instead of just usage."""
        self.print_help(sys.stderr)
        print(f"\nError: {message}", file=sys.stderr)
        sys.exit(2)


def add_plugin_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add plugin subcommand parser.

    Args:
        subparsers: The subparsers object to add the plugin parser to

    Returns:
        The plugin argument parser
    """
    description = """
Manage OpenHands plugins and plugin marketplaces.

Plugins extend OpenHands with additional skills, tools, and capabilities.
You can manage plugin marketplaces (registries) to discover and install plugins.

Examples:

  # Add a plugin marketplace
  openhands plugin marketplace add https://plugins.openhands.ai/index.json

  # Add a marketplace with a friendly name
  openhands plugin marketplace add https://plugins.openhands.ai/index.json --name "Official"

  # List configured marketplaces
  openhands plugin marketplace list

  # Remove a marketplace
  openhands plugin marketplace remove https://plugins.openhands.ai/index.json

  # Update marketplace indexes
  openhands plugin marketplace update

  # Update a specific marketplace
  openhands plugin marketplace update https://plugins.openhands.ai/index.json
"""
    plugin_parser = subparsers.add_parser(
        "plugin",
        help="Manage plugins and plugin marketplaces",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    plugin_subparsers = plugin_parser.add_subparsers(
        dest="plugin_command",
        help="Plugin commands",
        required=True,
        parser_class=PluginArgumentParser,
    )

    # Add marketplace subcommand
    _add_marketplace_parser(plugin_subparsers)

    return plugin_parser


def _add_marketplace_parser(
    plugin_subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Add marketplace subcommand parser.

    Args:
        plugin_subparsers: The plugin subparsers object

    Returns:
        The marketplace argument parser
    """
    marketplace_description = """
Manage plugin marketplaces (registries).

Marketplaces are URLs that provide an index of available plugins.
Configure marketplaces to discover and install plugins.

Examples:

  # Add a marketplace
  openhands plugin marketplace add https://plugins.openhands.ai/index.json

  # Add with a name
  openhands plugin marketplace add https://plugins.openhands.ai/index.json --name "Official"

  # List all marketplaces
  openhands plugin marketplace list

  # Remove a marketplace
  openhands plugin marketplace remove https://plugins.openhands.ai/index.json

  # Update all marketplace indexes
  openhands plugin marketplace update
"""
    marketplace_parser = plugin_subparsers.add_parser(
        "marketplace",
        help="Manage plugin marketplaces",
        description=marketplace_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    marketplace_subparsers = marketplace_parser.add_subparsers(
        dest="marketplace_command",
        help="Marketplace commands",
        required=True,
        parser_class=PluginArgumentParser,
    )

    # marketplace add command
    add_description = """
Add a new plugin marketplace.

Examples:

  # Add a marketplace
  openhands plugin marketplace add https://plugins.openhands.ai/index.json

  # Add with a friendly name
  openhands plugin marketplace add https://plugins.openhands.ai/index.json --name "Official"
"""
    add_parser = marketplace_subparsers.add_parser(
        "add",
        help="Add a plugin marketplace",
        description=add_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_parser.add_argument(
        "url",
        help="URL of the marketplace index (e.g., https://plugins.example.com/index.json)",
    )
    add_parser.add_argument(
        "--name",
        "-n",
        help="Friendly name for the marketplace",
    )

    # marketplace remove command
    remove_description = """
Remove a plugin marketplace.

Examples:

  # Remove a marketplace by URL
  openhands plugin marketplace remove https://plugins.openhands.ai/index.json
"""
    remove_parser = marketplace_subparsers.add_parser(
        "remove",
        help="Remove a plugin marketplace",
        description=remove_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    remove_parser.add_argument(
        "url",
        help="URL of the marketplace to remove",
    )

    # marketplace list command
    list_description = """
List all configured plugin marketplaces.

Examples:

  # List all marketplaces
  openhands plugin marketplace list
"""
    marketplace_subparsers.add_parser(
        "list",
        help="List all configured marketplaces",
        description=list_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # marketplace update command
    update_description = """
Update marketplace indexes.

This refreshes the local cache of available plugins from configured marketplaces.

Examples:

  # Update all marketplace indexes
  openhands plugin marketplace update

  # Update a specific marketplace
  openhands plugin marketplace update https://plugins.openhands.ai/index.json
"""
    update_parser = marketplace_subparsers.add_parser(
        "update",
        help="Update marketplace indexes",
        description=update_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    update_parser.add_argument(
        "url",
        nargs="?",
        help="URL of specific marketplace to update (optional, updates all if not specified)",
    )

    return marketplace_parser
