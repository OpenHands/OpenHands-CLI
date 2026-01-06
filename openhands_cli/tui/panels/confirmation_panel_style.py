INLINE_CONFIRMATION_PANEL_STYLE = """
InlineConfirmationPanel {
    width: 100%;
    height: auto;
    background: $background;
    padding: 0 1;
    margin: 1 0;
}

.inline-confirmation-content {
    width: 100%;
    height: auto;
}

.inline-confirmation-header {
    color: $primary;
    text-style: bold;
    height: auto;
    width: 100%;
    margin-bottom: 1;
}

.inline-confirmation-options {
    height: auto;
    width: 100%;
    background: transparent;
}

.inline-confirmation-options > ListItem {
    padding: 0;
    margin: 0;
    height: auto;
    background: transparent;
}

.inline-confirmation-options > ListItem:hover {
    background: transparent;
}

.inline-confirmation-options > ListItem.-highlighted {
    background: transparent;
}

.inline-confirmation-options Static {
    width: auto;
}
"""
