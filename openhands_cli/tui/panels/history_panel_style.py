"""CSS styles for the history side panel."""

HISTORY_PANEL_STYLE = """
    HistorySidePanel {
        split: right;
        width: 33%;
        min-width: 30;
        max-width: 60;
        border-left: vkey $foreground 30%;
        padding: 0 1;
        height: 1fr;
        padding-right: 1;
        layout: vertical;
        height: 100%;
    }

    .history-header {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
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
