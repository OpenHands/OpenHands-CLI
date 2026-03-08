from __future__ import annotations

from typing import Any, get_args, get_origin

from openhands_cli.stores.agent_store import AgentStore
from openhands_cli.stores.programmatic_settings import CliProgrammaticSettings


BOOLEAN_TRUE_VALUES = {"1", "true", "yes", "on", "enable", "enabled"}
BOOLEAN_FALSE_VALUES = {"0", "false", "no", "off", "disable", "disabled"}


def get_programmatic_setting_fields() -> list[Any]:
    schema = CliProgrammaticSettings.export_schema()
    return [
        field
        for section in schema.sections
        for field in section.fields
        if field.slash_command is not None
    ]


def get_programmatic_setting_command_map() -> dict[str, Any]:
    return {
        field.slash_command: field
        for field in get_programmatic_setting_fields()
        if field.slash_command is not None
    }


def handle_programmatic_setting_command(
    command: str,
    argument: str,
    *,
    agent_store: AgentStore | None = None,
) -> str | None:
    field = get_programmatic_setting_command_map().get(command)
    if field is None:
        return None

    settings = CliProgrammaticSettings.load(agent_store)
    if not argument.strip():
        return format_setting_command_help(field, settings)

    value = _parse_setting_value(field.key, field, argument)
    updated = settings.model_copy(update={field.key: value})
    updated.save(agent_store)
    return format_setting_update_message(field, value)


def format_setting_command_help(
    field: Any,
    settings: CliProgrammaticSettings,
) -> str:
    current_value = getattr(settings, field.key)
    lines = [f"/{field.slash_command} - {field.label}"]
    if field.description:
        lines.extend(["", field.description])
    lines.extend(["", f"Current value: {_display_value(field, current_value)}"])
    hint = _argument_hint(field)
    if hint:
        lines.extend(["", f"Usage: /{field.slash_command} {hint}"])
    return "\n".join(lines)


def format_setting_update_message(field: Any, value: Any) -> str:
    return f"{field.label} set to {_display_value(field, value)}"


def _argument_hint(field: Any) -> str:
    if field.widget == "boolean":
        return "on|off"
    if field.widget == "select":
        return "|".join(choice.value for choice in field.choices)
    if field.widget == "number":
        return "<number>"
    if field.secret:
        return "<secret>"
    return "<value>"


def _parse_setting_value(field_key: str, field: Any, argument: str) -> Any:
    raw_value = argument.strip()
    if field.widget == "boolean":
        normalized = raw_value.lower()
        if normalized in BOOLEAN_TRUE_VALUES:
            return True
        if normalized in BOOLEAN_FALSE_VALUES:
            return False
        raise ValueError(
            f"Expected one of: {sorted(BOOLEAN_TRUE_VALUES | BOOLEAN_FALSE_VALUES)}"
        )

    if field.widget == "select":
        allowed_values = {choice.value for choice in field.choices}
        if raw_value not in allowed_values:
            raise ValueError(f"Expected one of: {sorted(allowed_values)}")
        return raw_value

    annotation = CliProgrammaticSettings.model_fields[field_key].annotation
    inner = _strip_optional(annotation)
    if inner is int:
        return int(raw_value)
    if inner is float:
        return float(raw_value)
    return raw_value


def _display_value(field: Any, value: Any) -> str:
    if field.secret:
        return "<hidden>" if value else "<not set>"
    if isinstance(value, bool):
        return "enabled" if value else "disabled"
    return str(value)


def _strip_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is None:
        return annotation
    args = [arg for arg in get_args(annotation) if arg is not type(None)]
    if len(args) == 1:
        return args[0]
    return annotation
