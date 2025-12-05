"""OpenHands custom theme for textual UI."""

from textual.theme import Theme


def create_openhands_theme() -> Theme:
    """Create and return the custom OpenHands theme."""
    return Theme(
        name="openhands",
        primary="#ffe165",  # Logo, cursor color
        secondary="#ffffff",  # Borders, plain text
        accent="#277dff",  # Special text like "initialize conversation"
        foreground="#ffffff",  # Default text color
        background="#222222",  # Background color
        surface="#222222",  # Surface color (same as background)
        panel="#222222",  # Panel color (same as background)
        success="#ffe165",  # Success messages (use logo color)
        warning="#ffe165",  # Warning messages (use logo color)
        error="#ff6b6b",  # Error messages (light red)
        dark=True,  # This is a dark theme
        variables={
            # Placeholder text color
            "input-placeholder-foreground": "#727987",
            # Selection colors
            "input-selection-background": "#ffe165 20%",
        },
    )


# Create the theme instance
OPENHANDS_THEME = create_openhands_theme()
