INLINE_CONFIRMATION_PANEL_STYLE = """
InlineConfirmationPanel {
    width: 100%;
    height: auto;
    background: $surface;
    padding: 1;
    margin: 1 0;
    border: solid $primary;
}

.inline-confirmation-content {
    width: 100%;
    height: auto;
    align: center middle;
}

.inline-confirmation-header {
    color: $primary;
    text-style: bold;
    height: auto;
    width: auto;
    padding-right: 1;
}

.inline-confirmation-options {
    height: auto;
    width: 1fr;
    background: $background;
    border: solid $secondary;
}

.inline-confirmation-options > ListItem {
    padding: 0 2;
    margin: 0;
    height: auto;
}

.inline-confirmation-options > ListItem:hover {
    background: $surface;
}

.inline-confirmation-options > ListItem.-highlighted {
    background: $primary;
    color: $foreground;
}

.inline-confirmation-options Static {
    width: auto;
}
"""
