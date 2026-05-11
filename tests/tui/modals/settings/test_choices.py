"""Tests for openhands_cli.tui.modals.settings.choices."""

from openhands_cli.tui.modals.settings.choices import get_provider_options


def test_openhands_provider_is_listed_first() -> None:
    """The 'openhands' provider should always be the first option.

    Regression test for #712: the dropdown was rendering providers strictly
    alphabetically, which pushed 'openhands' below entries like 'anthropic'.
    """
    options = get_provider_options()
    assert options, "expected at least one provider option"

    first_value, first_label = options[0]
    assert first_value == "openhands"
    assert first_label == "openhands"


def test_remaining_providers_are_sorted_alphabetically() -> None:
    """All providers other than 'openhands' should remain alphabetically sorted."""
    options = get_provider_options()
    other_values = [value for value, _ in options if value != "openhands"]
    assert other_values == sorted(other_values)
