"""Tests for schema-driven settings slash command helpers."""

import pytest

from openhands_cli.shared.settings_commands import (
    format_setting_argument_hint,
    get_programmatic_setting_command_map,
)


class TestFormatSettingArgumentHint:
    """Tests for slash-command argument hint formatting."""

    @pytest.mark.parametrize(
        ("command", "separator", "expected"),
        [
            ("critic", "|", "on|off"),
            ("critic", " | ", "on | off"),
            ("issue-threshold", "|", "<number>"),
            ("llm-api-key", "|", "<secret>"),
            ("llm-model", "|", "<value>"),
        ],
    )
    def test_formats_expected_hints(
        self,
        command: str,
        separator: str,
        expected: str,
    ) -> None:
        """Hints should stay consistent anywhere settings commands are surfaced."""
        field = get_programmatic_setting_command_map()[command]

        assert format_setting_argument_hint(field, separator=separator) == expected
