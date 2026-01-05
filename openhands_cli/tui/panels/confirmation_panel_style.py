CONFIRMATION_SIDE_PANEL_STYLE = """
ConfirmationSidePanel {
    split: right;
    width: 33%;
    height: 100%;
    border-left: vkey $foreground 30%;
    background: $surface;
    padding: 1;
    margin-left: 1;
    scrollbar-size-vertical: 1;
}

ConfirmationPanel {
    height: auto;
    width: 100%;
}

.confirmation-content {
    height: auto;
    width: 100%;
}

.confirmation-header {
    color: $primary;
    text-style: bold;
    margin-bottom: 1;
    height: auto;
}

.actions-container {
    height: auto;
    margin-bottom: 1;
}

.action-item {
    color: $foreground;
    margin-bottom: 1;
    padding: 0 1;
    background: $background;
    border: solid $secondary;
}

.confirmation-instructions {
    color: $secondary;
    text-style: italic;
    margin-bottom: 1;
    text-align: center;
}

.confirmation-options {
    height: auto;
    border: solid $secondary;
    background: $background;
}

.confirmation-options > ListItem {
    padding: 1 2;
    margin: 0;
}

.confirmation-options > ListItem:hover {
    background: $background;
}

.confirmation-options > ListItem.-highlighted {
    background: $primary;
    color: $foreground;
}

.confirmation-options Static {
    width: 100%;
}
"""
