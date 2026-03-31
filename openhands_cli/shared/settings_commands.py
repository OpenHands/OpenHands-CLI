from __future__ import annotations

from dataclasses import dataclass
from typing import Any, get_args, get_origin

from pydantic import BaseModel

from openhands.sdk.settings import SettingsChoice, SettingsFieldSchema
from openhands_cli.stores.agent_store import AgentStore
from openhands_cli.stores.programmatic_settings import CliProgrammaticSettings


BOOLEAN_TRUE_VALUES = {"1", "true", "yes", "on", "enable", "enabled"}
BOOLEAN_FALSE_VALUES = {"0", "false", "no", "off", "disable", "disabled"}
PROGRAMMATIC_FIELD_OVERRIDES = {
    "condenser.enabled": "condenser",
    "verification.critic_enabled": "critic",
}
PROGRAMMATIC_FIELD_SKIP_KEYS = {
    "verification.confirmation_mode",
    "verification.security_analyzer",
}
PROGRAMMATIC_FIELD_DROP_SECTION_PREFIXES = {"cli", "verification"}
SUPPORTED_PROGRAMMATIC_VALUE_TYPES = {"boolean", "integer", "number", "string"}


@dataclass(frozen=True)
class ProgrammaticSettingField:
    key: str
    label: str
    description: str | None
    section_label: str
    value_type: str
    secret: bool
    choices: tuple[SettingsChoice, ...]
    widget: str
    slash_command: str


def get_programmatic_setting_fields() -> list[ProgrammaticSettingField]:
    schema = CliProgrammaticSettings.export_schema()
    fields: list[ProgrammaticSettingField] = []
    for section in schema.sections:
        for field in section.fields:
            programmatic_field = _to_programmatic_setting_field(field)
            if programmatic_field is not None:
                fields.append(programmatic_field)
    return fields


def get_programmatic_setting_command_map() -> dict[str, ProgrammaticSettingField]:
    return {field.slash_command: field for field in get_programmatic_setting_fields()}


def get_programmatic_setting_value(settings: BaseModel, field_key: str) -> Any:
    value: Any = settings
    for part in field_key.split("."):
        value = getattr(value, part)
    return value


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
    updated = _update_setting_value(settings, field.key, value)
    updated.save(agent_store)
    return format_setting_update_message(field, value)


def format_setting_command_help(
    field: ProgrammaticSettingField,
    settings: CliProgrammaticSettings,
) -> str:
    current_value = get_programmatic_setting_value(settings, field.key)
    lines = [f"/{field.slash_command} - {field.label}"]
    if field.description:
        lines.extend(["", field.description])
    lines.extend(["", f"Current value: {_display_value(field, current_value)}"])
    hint = format_setting_argument_hint(field)
    if hint:
        lines.extend(["", f"Usage: /{field.slash_command} {hint}"])
    return "\n".join(lines)


def format_setting_update_message(field: ProgrammaticSettingField, value: Any) -> str:
    return f"{field.label} set to {_display_value(field, value)}"


def format_setting_argument_hint(
    field: ProgrammaticSettingField,
    *,
    separator: str = "|",
) -> str:
    if field.widget == "boolean":
        return separator.join(("on", "off"))
    if field.widget == "select":
        return separator.join(str(choice.value) for choice in field.choices)
    if field.widget == "number":
        return "<number>"
    if field.secret:
        return "<secret>"
    return "<value>"


def _parse_setting_value(
    field_key: str,
    field: ProgrammaticSettingField,
    argument: str,
) -> Any:
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

    annotation = _get_field_annotation(CliProgrammaticSettings, field_key)
    inner = _strip_optional(annotation)
    if inner is int:
        try:
            return int(raw_value)
        except ValueError as exc:
            raise ValueError(f"Expected an integer, got: {raw_value!r}") from exc
    if inner is float:
        try:
            return float(raw_value)
        except ValueError as exc:
            raise ValueError(f"Expected a number, got: {raw_value!r}") from exc
    return raw_value


def _display_value(field: ProgrammaticSettingField, value: Any) -> str:
    if field.secret:
        return "<hidden>" if value else "<not set>"
    if isinstance(value, bool):
        return "enabled" if value else "disabled"
    return str(value)


def _get_field_annotation(model_type: type[BaseModel], field_key: str) -> Any:
    current_model = model_type
    parts = field_key.split(".")
    for index, part in enumerate(parts):
        field = current_model.model_fields[part]
        if index == len(parts) - 1:
            return field.annotation
        inner = _strip_optional(field.annotation)
        assert isinstance(inner, type) and issubclass(inner, BaseModel)
        current_model = inner
    raise KeyError(field_key)


def _update_setting_value(
    settings: CliProgrammaticSettings,
    field_key: str,
    value: Any,
) -> CliProgrammaticSettings:
    parts = field_key.split(".")
    if len(parts) == 1:
        return settings.model_copy(update={parts[0]: value})

    nested_setting = getattr(settings, parts[0])
    if not isinstance(nested_setting, BaseModel):
        raise KeyError(field_key)
    return settings.model_copy(
        update={parts[0]: nested_setting.model_copy(update={parts[1]: value})}
    )


def _strip_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is None:
        return annotation
    args = [arg for arg in get_args(annotation) if arg is not type(None)]
    if len(args) == 1:
        return args[0]
    return annotation


def _to_programmatic_setting_field(
    field: SettingsFieldSchema,
) -> ProgrammaticSettingField | None:
    value_type = str(field.value_type)
    if field.key in PROGRAMMATIC_FIELD_SKIP_KEYS:
        return None
    if value_type not in SUPPORTED_PROGRAMMATIC_VALUE_TYPES:
        return None

    return ProgrammaticSettingField(
        key=field.key,
        label=field.label,
        description=field.description,
        section_label=field.section_label,
        value_type=value_type,
        secret=field.secret,
        choices=tuple(field.choices),
        widget=_derive_widget(field, value_type),
        slash_command=_derive_slash_command(field),
    )


def _derive_widget(field: SettingsFieldSchema, value_type: str) -> str:
    if value_type == "boolean":
        return "boolean"
    if field.choices:
        return "select"
    if value_type in {"integer", "number"}:
        return "number"
    return "text"


def _derive_slash_command(field: SettingsFieldSchema) -> str:
    override = PROGRAMMATIC_FIELD_OVERRIDES.get(field.key)
    if override is not None:
        return override

    parts = field.key.split(".")
    if not parts:
        raise ValueError(f"Invalid settings field key: {field.key!r}")

    section, *rest = parts
    slug_parts = [part.replace("_", "-") for part in rest]
    if section not in PROGRAMMATIC_FIELD_DROP_SECTION_PREFIXES:
        slug_parts.insert(0, section.replace("_", "-"))
    return "-".join(slug_parts)
