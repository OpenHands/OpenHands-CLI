"""CSS styles for the Plan side panel."""

PLAN_PANEL_STYLE = """
    PlanSidePanel {
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

    .plan-header {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }

    .plan-task {
        margin-bottom: 0;
        padding: 0;
    }

    .plan-task-todo {
        color: $foreground;
    }

    .plan-task-in-progress {
        color: $warning;
    }

    .plan-task-done {
        color: $success;
    }

    .plan-empty {
        color: $foreground;
        text-style: italic;
    }

    .plan-notes {
        color: $foreground 70%;
        margin-left: 2;
        text-style: italic;
    }
"""
