"""Tests for the OpenHands theme module."""

from textual.theme import Theme

from openhands_cli.theme import OPENHANDS_THEME, create_openhands_theme


class TestOpenHandsTheme:
    """Tests for the OpenHands theme functionality."""

    def test_create_openhands_theme(self):
        """Test that create_openhands_theme returns a valid Theme object."""
        theme = create_openhands_theme()

        assert isinstance(theme, Theme)
        assert theme.name == "openhands"
        assert theme.dark is True

    def test_theme_variables(self):
        """Test that theme has correct custom variables."""
        theme = create_openhands_theme()

        # Test custom variables
        assert "input-placeholder-foreground" in theme.variables
        assert theme.variables["input-placeholder-foreground"] == "#727987"

        assert "input-selection-background" in theme.variables
        assert theme.variables["input-selection-background"] == "#ffe165 20%"

    def test_openhands_theme_constant(self):
        """Test that OPENHANDS_THEME constant is properly initialized."""
        assert isinstance(OPENHANDS_THEME, Theme)
        assert OPENHANDS_THEME.name == "openhands"

        # Should be the same as calling create_openhands_theme()
        created_theme = create_openhands_theme()
        assert OPENHANDS_THEME.name == created_theme.name
        assert OPENHANDS_THEME.primary == created_theme.primary
        assert OPENHANDS_THEME.secondary == created_theme.secondary
        assert OPENHANDS_THEME.accent == created_theme.accent
        assert OPENHANDS_THEME.background == created_theme.background

    def test_theme_consistency(self):
        """Test that multiple calls to create_openhands_theme are consistent."""
        theme1 = create_openhands_theme()
        theme2 = create_openhands_theme()

        # Should have same properties
        assert theme1.name == theme2.name
        assert theme1.primary == theme2.primary
        assert theme1.secondary == theme2.secondary
        assert theme1.accent == theme2.accent
        assert theme1.background == theme2.background
        assert theme1.variables == theme2.variables
