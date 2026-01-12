"""CSS styles for the Plan side panel."""

PLAN_PANEL_STYLE = """
    PlanSidePanel {
        split: right;
        width: 33%;
        min-width: 30;
        max-width: 60;
        border-left: vkey $foreground 30%;
        padding: 0 1;
        padding-right: 1;
        layout: vertical;
        height: 100%;
    }

    .plan-header-row {
        width: 100%;
        height: 1;
        align-vertical: middle;
        margin-bottom: 1;
    }

    .plan-header {
        color: $primary;
        text-style: bold;
        width: 1fr;
        height: 1;
    }

    #plan-close-btn {
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

    #plan-close-btn:hover {
        background: #333333;
        color: $error;
        border: none;
    }

    #plan-close-btn:focus {
        background: transparent;
        color: #aaaaaa;
        border: none;
        text-style: bold;
    }

    #plan-close-btn.-active {
        background: #333333;
        color: $error;
        border: none;
    }
"""
