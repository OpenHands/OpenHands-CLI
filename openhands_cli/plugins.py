"""Plugin loading utilities for OpenHands CLI.

This module provides functionality to load plugins from custom directories
specified via the --plugins-dir CLI flag. Similar to Claude Code's
--plugin-dir flag, this allows loading plugins for a session only.

Plugins can include skills, hooks, MCP configurations, agents, and commands.
"""

from pathlib import Path

from rich.console import Console

from openhands.sdk.logger import get_logger
from openhands.sdk.plugin import Plugin


logger = get_logger(__name__)
console = Console()


def load_plugins_from_dirs(plugins_dirs: list[str]) -> list[Plugin]:
    """Load plugins from custom directories.

    Each directory can be either:
    - A specific plugin directory (containing .plugin/ or .claude-plugin/)
    - A directory containing multiple plugin subdirectories

    Args:
        plugins_dirs: List of directory paths to load plugins from.

    Returns:
        List of Plugin objects loaded from the directories.
    """
    all_plugins: list[Plugin] = []
    seen_names: set[str] = set()

    for dir_path in plugins_dirs:
        path = Path(dir_path).expanduser().resolve()

        if not path.exists():
            console.print(
                f"[yellow]Warning:[/yellow] Plugins directory does not exist: {path}"
            )
            logger.warning(f"Plugins directory does not exist: {path}")
            continue

        if not path.is_dir():
            console.print(
                f"[yellow]Warning:[/yellow] Plugins path is not a directory: {path}"
            )
            logger.warning(f"Plugins path is not a directory: {path}")
            continue

        plugins = _load_plugins_from_path(path, seen_names)
        all_plugins.extend(plugins)

    return all_plugins


def _is_plugin_directory(path: Path) -> bool:
    """Check if a directory looks like a plugin directory.

    A plugin directory has either .plugin/ or .claude-plugin/ with plugin.json.
    """
    for manifest_dir in [".plugin", ".claude-plugin"]:
        manifest_path = path / manifest_dir / "plugin.json"
        if manifest_path.exists():
            return True
    return False


def _load_plugins_from_path(path: Path, seen_names: set[str]) -> list[Plugin]:
    """Load plugins from a single path.

    If the path looks like a plugin directory (has .plugin/ or .claude-plugin/),
    load it as a single plugin. Otherwise, try loading all plugins from
    subdirectories.

    Args:
        path: Path to the directory to load plugins from.
        seen_names: Set of plugin names already seen (for deduplication).

    Returns:
        List of Plugin objects loaded from the path.
    """
    plugins: list[Plugin] = []

    # Check if this is a plugin directory (has manifest)
    if _is_plugin_directory(path):
        try:
            plugin = Plugin.load(path)
            if plugin.name not in seen_names:
                plugins.append(plugin)
                seen_names.add(plugin.name)
                console.print(
                    f"[green]✓[/green] Loaded plugin '{plugin.name}' from {path} "
                    f"({len(plugin.skills)} skills, "
                    f"hooks={'yes' if plugin.hooks else 'no'}, "
                    f"mcp={'yes' if plugin.mcp_config else 'no'})"
                )
                logger.info(f"Loaded plugin '{plugin.name}' from {path}")
            else:
                console.print(
                    f"[yellow]Warning:[/yellow] Skipping duplicate plugin "
                    f"'{plugin.name}' from {path}"
                )
                logger.warning(f"Skipping duplicate plugin '{plugin.name}' from {path}")
            return plugins
        except Exception as e:
            logger.warning(f"Failed to load plugin from {path}: {e}")
            console.print(
                f"[yellow]Warning:[/yellow] Failed to load plugin from {path}: {e}"
            )
            return plugins

    # Not a plugin directory - try loading plugins from subdirectories
    try:
        loaded_plugins = Plugin.load_all(path)
        for plugin in loaded_plugins:
            if plugin.name not in seen_names:
                plugins.append(plugin)
                seen_names.add(plugin.name)
                console.print(
                    f"[green]✓[/green] Loaded plugin '{plugin.name}' from {path} "
                    f"({len(plugin.skills)} skills, "
                    f"hooks={'yes' if plugin.hooks else 'no'}, "
                    f"mcp={'yes' if plugin.mcp_config else 'no'})"
                )
                logger.info(f"Loaded plugin '{plugin.name}' from {path}")
            else:
                console.print(
                    f"[yellow]Warning:[/yellow] Skipping duplicate plugin "
                    f"'{plugin.name}' from {path}"
                )
                logger.warning(
                    f"Skipping duplicate plugin '{plugin.name}' from {path}"
                )
    except Exception as e:
        logger.debug(f"Could not load plugins from {path}: {e}")

    if not plugins:
        console.print(f"[yellow]Warning:[/yellow] No plugins found in {path}")
        logger.warning(f"No plugins found in {path}")

    return plugins
