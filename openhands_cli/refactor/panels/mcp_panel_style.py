MCP_PANEL_STYLE = """
    MCPSidePanel {
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
    .mcp-header {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }

    .mcp-section {
        margin-bottom: 1;
    }

    .mcp-server-name {
        color: $primary;
        text-style: bold;
    }

    .mcp-server-detail {
        color: $foreground;
        margin-left: 2;
    }

    .mcp-status {
        color: $accent;
        margin-bottom: 1;
    }

    .mcp-no-servers {
        color: $warning;
        text-style: italic;
    }

    .mcp-error {
        color: $error;
    }
"""
