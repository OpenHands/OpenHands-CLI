"""Plugin loading utilities for OpenHands CLI.

This module provides functionality to load plugins (skills) from custom
directories specified via the --plugins-dir CLI flag. Similar to Claude
Code's --plugin-dir flag, this allows loading skills for a session only.
"""

from pathlib import Path

from rich.console import Console

from openhands.sdk.context import Skill
from openhands.sdk.context.skills.skill import load_skills_from_dir
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)
console = Console()


def load_skills_from_plugins_dirs(plugins_dirs: list[str]) -> list[Skill]:
    """Load skills from custom plugins directories.

    Each directory can be either:
    - A directory containing multiple plugins (subdirectories with skills)
    - A specific plugin directory containing skills directly

    Args:
        plugins_dirs: List of directory paths to load plugins from.

    Returns:
        List of Skill objects loaded from the plugins directories.
    """
    all_skills: list[Skill] = []
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

        try:
            # Try to load skills from the directory (handles both direct plugin
            # directories and directories containing multiple plugins)
            skills = _load_skills_from_dir(path, seen_names)
            all_skills.extend(skills)

            if skills:
                console.print(
                    f"[green]✓[/green] Loaded {len(skills)} skill(s) from {path}"
                )
                logger.info(
                    f"Loaded {len(skills)} skills from plugins dir {path}: "
                    f"{[s.name for s in skills]}"
                )
        except Exception as e:
            console.print(
                f"[yellow]Warning:[/yellow] Failed to load plugins from {path}: {e}"
            )
            logger.warning(f"Failed to load plugins from {path}: {e}")

    return all_skills


def _load_skills_from_dir(path: Path, seen_names: set[str]) -> list[Skill]:
    """Load skills from a single directory.

    Attempts to load skills using the SDK's load_skills_from_dir function.
    Also checks subdirectories if the directory appears to contain multiple plugins.

    Args:
        path: Path to the directory to load skills from.
        seen_names: Set of skill names already seen (for deduplication).

    Returns:
        List of Skill objects loaded from the directory.
    """
    skills: list[Skill] = []

    # Try loading skills directly from this directory
    try:
        repo_skills, knowledge_skills, agent_skills = load_skills_from_dir(path)

        for skills_dict in [repo_skills, knowledge_skills, agent_skills]:
            for name, skill in skills_dict.items():
                if name not in seen_names:
                    skills.append(skill)
                    seen_names.add(name)
                else:
                    logger.warning(f"Skipping duplicate skill '{name}' from {path}")
    except Exception as e:
        logger.debug(f"Could not load skills directly from {path}: {e}")

    # If no skills were loaded directly, check if this is a directory containing
    # multiple plugin subdirectories
    if not skills:
        for subdir in path.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("."):
                try:
                    repo_skills, knowledge_skills, agent_skills = load_skills_from_dir(
                        subdir
                    )

                    for skills_dict in [repo_skills, knowledge_skills, agent_skills]:
                        for name, skill in skills_dict.items():
                            if name not in seen_names:
                                skills.append(skill)
                                seen_names.add(name)
                            else:
                                logger.warning(
                                    f"Skipping duplicate skill '{name}' from {subdir}"
                                )
                except Exception as e:
                    logger.debug(f"Could not load skills from {subdir}: {e}")

    return skills
