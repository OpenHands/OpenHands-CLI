"""Skill lifecycle command handlers for the TUI.

Wraps the SDK's public skill management API (openhands.sdk.skills)
and renders results into the TUI scroll view.
"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Static

from openhands_cli.theme import OPENHANDS_THEME


_ERR = OPENHANDS_THEME.error
_OK = OPENHANDS_THEME.success
_WARN = OPENHANDS_THEME.warning


def handle_skill_command(scroll_view: VerticalScroll, args: str) -> None:
    """Route /skill <subcommand> to the appropriate handler."""
    parts = args.strip().split(None, 1)
    subcommand = parts[0] if parts else ""
    sub_args = parts[1].strip() if len(parts) > 1 else ""

    match subcommand:
        case "install":
            _skill_install(scroll_view, sub_args)
        case "list":
            _skill_list(scroll_view)
        case "enable":
            _skill_enable(scroll_view, sub_args)
        case "disable":
            _skill_disable(scroll_view, sub_args)
        case "uninstall":
            _skill_uninstall(scroll_view, sub_args)
        case "update":
            _skill_update(scroll_view, sub_args)
        case _:
            _skill_help(scroll_view)


def _mount(scroll_view: VerticalScroll, text: str) -> None:
    scroll_view.mount(Static(text, classes="skill-command-message"))
    scroll_view.scroll_end(animate=False)


def _skill_help(scroll_view: VerticalScroll) -> None:
    s = OPENHANDS_THEME.secondary
    p = OPENHANDS_THEME.primary
    _mount(
        scroll_view,
        f"""
[bold {p}]Skill Management[/bold {p}]
[dim]Usage:[/dim] /skill <subcommand>

  [{s}]install <source>[/{s}] - Install a skill
  [{s}]list[/{s}]              - List installed skills
  [{s}]enable <name>[/{s}]     - Enable a skill
  [{s}]disable <name>[/{s}]    - Disable a skill
  [{s}]uninstall <name>[/{s}]  - Uninstall a skill
  [{s}]update <name>[/{s}]     - Update a skill
""",
    )


def _skill_install(scroll_view: VerticalScroll, source: str) -> None:
    if not source:
        _mount(
            scroll_view,
            f"[{_ERR}]Usage: /skill install <source>[/]",
        )
        return
    try:
        from openhands.sdk.skills import install_skill

        info = install_skill(source)
        _mount(
            scroll_view,
            f"[{_OK}]Installed skill '{info.name}'[/]\n"
            "Restart your session to load the new skill.",
        )
    except Exception as e:
        _mount(
            scroll_view,
            f"[{_ERR}]Install failed: {e}[/]",
        )


def _skill_list(scroll_view: VerticalScroll) -> None:
    try:
        from openhands.sdk.skills import list_installed_skills

        skills = list_installed_skills()
        if not skills:
            _mount(
                scroll_view,
                "[dim]No installed skills.[/dim]",
            )
            return
        p = OPENHANDS_THEME.primary
        lines = [f"\n[bold {p}]Installed Skills ({len(skills)})[/bold {p}]"]
        for sk in skills:
            status = "✓ enabled" if sk.enabled else "✗ disabled"
            style = _OK if sk.enabled else _WARN
            desc = f" - {sk.description}" if sk.description else ""
            lines.append(f"  [{style}]{status}[/] {sk.name}{desc}")
        _mount(scroll_view, "\n".join(lines))
    except Exception as e:
        _mount(scroll_view, f"[{_ERR}]Error: {e}[/]")


def _skill_enable(scroll_view: VerticalScroll, name: str) -> None:
    if not name:
        _mount(
            scroll_view,
            f"[{_ERR}]Usage: /skill enable <name>[/]",
        )
        return
    try:
        from openhands.sdk.skills import enable_skill

        if enable_skill(name):
            _mount(
                scroll_view,
                f"[{_OK}]Enabled skill '{name}'[/]\nRestart your session to apply.",
            )
        else:
            _mount(
                scroll_view,
                f"[{_WARN}]Skill '{name}' not found.[/]",
            )
    except Exception as e:
        _mount(scroll_view, f"[{_ERR}]Error: {e}[/]")


def _skill_disable(scroll_view: VerticalScroll, name: str) -> None:
    if not name:
        _mount(
            scroll_view,
            f"[{_ERR}]Usage: /skill disable <name>[/]",
        )
        return
    try:
        from openhands.sdk.skills import disable_skill

        if disable_skill(name):
            _mount(
                scroll_view,
                f"[{_OK}]Disabled skill '{name}'[/]\nRestart your session to apply.",
            )
        else:
            _mount(
                scroll_view,
                f"[{_WARN}]Skill '{name}' not found.[/]",
            )
    except Exception as e:
        _mount(scroll_view, f"[{_ERR}]Error: {e}[/]")


def _skill_uninstall(scroll_view: VerticalScroll, name: str) -> None:
    if not name:
        _mount(
            scroll_view,
            f"[{_ERR}]Usage: /skill uninstall <name>[/]",
        )
        return
    try:
        from openhands.sdk.skills import uninstall_skill

        if uninstall_skill(name):
            _mount(
                scroll_view,
                f"[{_OK}]Uninstalled skill '{name}'[/]",
            )
        else:
            _mount(
                scroll_view,
                f"[{_WARN}]Skill '{name}' not found.[/]",
            )
    except Exception as e:
        _mount(scroll_view, f"[{_ERR}]Error: {e}[/]")


def _skill_update(scroll_view: VerticalScroll, name: str) -> None:
    if not name:
        _mount(
            scroll_view,
            f"[{_ERR}]Usage: /skill update <name>[/]",
        )
        return
    try:
        from openhands.sdk.skills import update_skill

        info = update_skill(name)
        if info:
            _mount(
                scroll_view,
                f"[{_OK}]Updated skill '{info.name}'[/]\n"
                "Restart your session to apply.",
            )
        else:
            _mount(
                scroll_view,
                f"[{_WARN}]Skill '{name}' not found.[/]",
            )
    except Exception as e:
        _mount(scroll_view, f"[{_ERR}]Error: {e}[/]")
