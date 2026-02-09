"""CSS styles for the history side panel."""

HISTORY_PANEL_STYLE = """
    HistorySidePanel {
        split: right;
        width: 33%;
        min-width: 30;
        max-width: 60;
        border-left: vkey $foreground 30%;
        padding: 0 1;
        layout: vertical;
        height: 100%;
    }

    .history-header-row {
        width: 100%;
        height: 1;
        align-vertical: middle;
        margin-bottom: 1;
    }

    .history-header {
        color: $primary;
        text-style: bold;
        width: 1fr;
        height: 1;
    }

    #history-close-btn {
        min-width: 3;
        width: auto;
        height: 1;
        background: transparent;
        color: #aaaaaa;
        border: none;
        padding: 0;
        margin: 0;
        text-style: bold;
    }

    #history-close-btn:hover {
        background: #333333;
        color: $error;
        border: none;
    }

    #history-close-btn:focus {
        background: transparent;
        color: #aaaaaa;
        border: none;
        text-style: bold;
    }

    .history-item {
        padding: 0 1;
        height: 2;
    }

    .history-item:hover {
        background: $primary 20%;
    }

    .history-item-current {
        background: $primary 40%;
    }

    .history-item-selected {
        background: $primary 25%;
    }

    .history-empty {
        color: $warning;
        text-style: italic;
        margin-top: 1;
    }

    .history-loading {
        color: $primary;
        text-style: italic;
        margin-top: 1;
    }

    #history-list {
        height: 1fr;
        overflow-y: auto;
        scrollbar-size-vertical: 1;
    }
"""
