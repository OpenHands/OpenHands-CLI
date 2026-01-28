"""Plugin loader module for loading enabled plugins into conversations.

This module handles loading enabled plugins from storage and converting them
into Skills that can be passed to the agent.
"""

from typing import Any

from openhands.sdk.context import Skill

from openhands_cli.plugins.marketplace_storage import MarketplaceStorage
from openhands_cli.plugins.plugin_storage import InstalledPlugin, PluginStorage


class PluginLoadError(Exception):
    """Exception raised when a plugin fails to load."""

    pass


def load_enabled_plugins() -> list[Skill]:
    """Load all enabled plugins and convert them to Skills.

    Returns:
        List of Skill objects for enabled plugins.
    """
    plugin_storage = PluginStorage()
    marketplace_storage = MarketplaceStorage()

    enabled_plugins = plugin_storage.get_enabled_plugins()

    if not enabled_plugins:
        return []

    skills = []
    for plugin in enabled_plugins:
        try:
            skill = _load_plugin_as_skill(plugin, marketplace_storage)
            if skill:
                skills.append(skill)
        except PluginLoadError:
            # Log but continue loading other plugins
            # In a production system, you might want to notify the user
            pass

    return skills


def _load_plugin_as_skill(
    plugin: InstalledPlugin, marketplace_storage: MarketplaceStorage
) -> Skill | None:
    """Load a single plugin and convert it to a Skill.

    Args:
        plugin: The installed plugin to load.
        marketplace_storage: Storage for accessing marketplace indexes.

    Returns:
        Skill object if the plugin was loaded successfully, None otherwise.

    Raises:
        PluginLoadError: If the plugin cannot be loaded.
    """
    # Get the cached marketplace index
    cached_index = marketplace_storage.get_cached_index(plugin.marketplace)

    if not cached_index:
        raise PluginLoadError(
            f"Marketplace index not found for '{plugin.marketplace}'. "
            f"Run 'openhands plugin marketplace update {plugin.marketplace}' to fetch it."
        )

    # Find the plugin definition in the marketplace index
    plugin_def = _find_plugin_in_index(plugin.name, cached_index)

    if not plugin_def:
        raise PluginLoadError(
            f"Plugin '{plugin.name}' not found in marketplace '{plugin.marketplace}' index."
        )

    # Create a Skill from the plugin definition
    return _create_skill_from_plugin(plugin, plugin_def)


def _find_plugin_in_index(
    plugin_name: str, index: dict[str, Any]
) -> dict[str, Any] | None:
    """Find a plugin definition in a marketplace index.

    Args:
        plugin_name: Name of the plugin to find.
        index: Marketplace index data.

    Returns:
        Plugin definition dict if found, None otherwise.
    """
    plugins = index.get("plugins", [])

    for p in plugins:
        if p.get("name") == plugin_name:
            return p

    return None


def _create_skill_from_plugin(
    plugin: InstalledPlugin, plugin_def: dict[str, Any]
) -> Skill:
    """Create a Skill from a plugin definition.

    The skill content is built from the plugin's description and instructions.
    This provides the agent with context about the plugin's capabilities.

    Args:
        plugin: The installed plugin metadata.
        plugin_def: Plugin definition from the marketplace index.

    Returns:
        Skill object representing the plugin.
    """
    # Build skill content from plugin definition
    name = plugin_def.get("name", plugin.name)
    description = plugin_def.get("description", "")
    instructions = plugin_def.get("instructions", "")

    # Combine description and instructions for the skill content
    content_parts = []

    if description:
        content_parts.append(description)

    if instructions:
        content_parts.append(instructions)

    # If no content provided, use a default message
    if not content_parts:
        content_parts.append(
            f"Plugin '{name}' is enabled. "
            f"Use its capabilities as needed."
        )

    content = "\n\n".join(content_parts)

    # Note: Skill triggers require KeywordTrigger or TaskTrigger objects,
    # which are complex types. For now, plugins don't support triggers.
    # In the future, this could be extended to parse trigger definitions.

    return Skill(
        name=f"plugin:{plugin.full_name}",
        content=content,
        description=description or None,
    )


def get_plugin_skills_summary() -> str:
    """Get a summary of enabled plugins for display.

    Returns:
        String summary of enabled plugins.
    """
    plugin_storage = PluginStorage()
    enabled_plugins = plugin_storage.get_enabled_plugins()

    if not enabled_plugins:
        return "No plugins enabled"

    plugin_names = [p.full_name for p in enabled_plugins]
    return f"Enabled plugins: {', '.join(plugin_names)}"
