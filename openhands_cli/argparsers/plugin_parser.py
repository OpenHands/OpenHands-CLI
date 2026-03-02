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

  # Add a plugin marketplace using GitHub shorthand
  openhands plugin marketplace add company/plugins

  # Add with explicit GitHub prefix
  openhands plugin marketplace add github:openhands/community-plugins

  # Add a Git repository
  openhands plugin marketplace add https://gitlab.com/org/plugins.git

  # Add a direct URL to marketplace index
  openhands plugin marketplace add https://plugins.example.com/marketplace.json

  # Add with a custom name
  openhands plugin marketplace add company/plugins --name my-plugins

  # List configured marketplaces
  openhands plugin marketplace list

  # Remove a marketplace by name
  openhands plugin marketplace remove company-plugins

  # Update all marketplace indexes
  openhands plugin marketplace update

  # Update a specific marketplace
  openhands plugin marketplace update company-plugins
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

Marketplaces provide an index of available plugins. Supported source formats:
  - GitHub shorthand: owner/repo
  - Explicit GitHub: github:owner/repo
  - Git URL: https://gitlab.com/org/plugins.git
  - Direct URL: https://example.com/marketplace.json

Examples:

  # Add a marketplace using GitHub shorthand
  openhands plugin marketplace add company/plugins

  # Add with a custom name
  openhands plugin marketplace add company/plugins --name my-plugins

  # List all marketplaces
  openhands plugin marketplace list

  # Remove a marketplace by name
  openhands plugin marketplace remove company-plugins

  # Update all marketplace indexes
  openhands plugin marketplace update

  # Update a specific marketplace
  openhands plugin marketplace update company-plugins
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

Supported source formats:
  - GitHub shorthand: owner/repo
  - Explicit GitHub: github:owner/repo
  - Git URL: https://gitlab.com/org/plugins.git
  - Direct URL: https://example.com/marketplace.json

Examples:

  # Add using GitHub shorthand
  openhands plugin marketplace add company/plugins

  # Add with explicit GitHub prefix
  openhands plugin marketplace add github:openhands/community-plugins

  # Add a Git repository
  openhands plugin marketplace add https://gitlab.com/org/plugins.git

  # Add with a custom name
  openhands plugin marketplace add company/plugins --name my-plugins
"""
    add_parser = marketplace_subparsers.add_parser(
        "add",
        help="Add a plugin marketplace",
        description=add_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_parser.add_argument(
        "source",
        help="Marketplace source (GitHub: owner/repo, Git URL, or direct URL)",
    )
    add_parser.add_argument(
        "--name",
        "-n",
        help="Custom name for the marketplace (auto-generated if not provided)",
    )

    # marketplace remove command
    remove_description = """
Remove a plugin marketplace.

Examples:

  # Remove a marketplace by name
  openhands plugin marketplace remove company-plugins
"""
    remove_parser = marketplace_subparsers.add_parser(
        "remove",
        help="Remove a plugin marketplace",
        description=remove_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    remove_parser.add_argument(
        "name",
        help="Name of the marketplace to remove",
    )

    # marketplace list command
    list_description = """
List all configured plugin marketplaces.

Displays configured marketplaces with their source, auto-update setting,
and timestamps.

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
  openhands plugin marketplace update company-plugins
"""
    update_parser = marketplace_subparsers.add_parser(
        "update",
        help="Update marketplace indexes",
        description=update_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    update_parser.add_argument(
        "name",
        nargs="?",
        help="Name of specific marketplace to update (optional, updates all if not specified)",
    )

    return marketplace_parser
