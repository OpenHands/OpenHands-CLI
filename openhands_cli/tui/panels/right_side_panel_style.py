"""CSS styles for the Right Side Panel container."""

RIGHT_SIDE_PANEL_STYLE = """
    RightSidePanel {
        split: right;
        width: 33%;
        min-width: 30;
        max-width: 60;
        border-left: vkey $foreground 30%;
        layout: vertical;
        height: 100%;
        overflow: hidden;
    }

    .right-panel-divider {
        width: 100%;
        height: 1;
        background: #444444;
        margin: 1 0;
    }

    #right-panel-close-btn {
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

    #right-panel-close-btn:hover {
        background: #333333;
        color: $error;
        border: none;
    }

    #right-panel-close-btn:focus {
        background: transparent;
        color: #aaaaaa;
        border: none;
        text-style: bold;
    }

    #right-panel-close-btn.-active {
        background: #333333;
        color: $error;
        border: none;
    }

    .right-panel-header-row {
        width: 100%;
        height: auto;
        align-vertical: middle;
        padding: 0 1;
    }

    .right-panel-header {
        color: $primary;
        text-style: bold;
        width: 1fr;
        height: 1;
    }

    /* Override PlanSidePanel styles when inside RightSidePanel */
    RightSidePanel > PlanSidePanel {
        width: 100% !important;
        min-width: 0;
        max-width: 100%;
        border-left: none;
        height: 1fr !important;
        min-height: 5;
        padding: 0 1;
        split: none !important;
    }

    RightSidePanel .plan-header-row {
        display: none;
    }

    /* Override AskAgentPanel styles when inside RightSidePanel */
    RightSidePanel > AskAgentPanel {
        width: 100% !important;
        height: 1fr !important;
        min-height: 12;
    }
"""
