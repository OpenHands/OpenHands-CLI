"""Plugin subcommand argument parser for OpenHands CLI."""

import argparse


def add_plugin_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the plugin subcommand parser.

    Args:
        subparsers: The subparsers action to add the plugin parser to
    """
    plugin_parser = subparsers.add_parser(
        "plugin",
        help="Manage installed plugins",
        description="Install, uninstall, list, and update plugins",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    openhands plugin list                           # List installed plugins
    openhands plugin install github:owner/repo      # Install from GitHub
    openhands plugin install github:owner/repo --ref v1.0.0  # Install specific version
    openhands plugin uninstall plugin-name          # Uninstall a plugin
    openhands plugin update plugin-name             # Update a plugin

Supported sources:
    github:owner/repo           GitHub repository shorthand
    https://github.com/owner/repo   Full git URL
    git@github.com:owner/repo.git   SSH git URL
    /local/path                 Local directory path
        """,
    )

    plugin_subparsers = plugin_parser.add_subparsers(
        dest="plugin_command",
        help="Plugin management commands",
    )

    # List command
    list_parser = plugin_subparsers.add_parser(
        "list",
        help="List installed plugins",
        description="Display all plugins installed in ~/.openhands/skills/installed/",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )

    # Install command
    install_parser = plugin_subparsers.add_parser(
        "install",
        help="Install a plugin from a source",
        description="Install a plugin from GitHub, git URL, or local path",
    )
    install_parser.add_argument(
        "source",
        type=str,
        help=(
            "Plugin source: 'github:owner/repo', git URL, or local path. "
            "Examples: 'github:owner/my-plugin', 'https://github.com/owner/repo'"
        ),
    )
    install_parser.add_argument(
        "--ref",
        type=str,
        help="Branch, tag, or commit to install (default: latest)",
    )
    install_parser.add_argument(
        "--repo-path",
        type=str,
        help="Subdirectory path within the repository (for monorepos)",
    )
    install_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing installation",
    )

    # Uninstall command
    uninstall_parser = plugin_subparsers.add_parser(
        "uninstall",
        help="Uninstall a plugin",
        description="Remove an installed plugin by name",
    )
    uninstall_parser.add_argument(
        "name",
        type=str,
        help="Name of the plugin to uninstall",
    )

    # Update command
    update_parser = plugin_subparsers.add_parser(
        "update",
        help="Update an installed plugin",
        description="Update a plugin to the latest version from its original source",
    )
    update_parser.add_argument(
        "name",
        type=str,
        help="Name of the plugin to update",
    )
