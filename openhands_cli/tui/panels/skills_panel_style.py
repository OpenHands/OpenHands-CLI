SKILLS_PANEL_STYLE = """
    SkillsSidePanel {
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
    .skills-header {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }

    .skills-section {
        margin-bottom: 1;
    }

    .skill-name {
        color: $primary;
        text-style: bold;
    }

    .skill-detail {
        color: $foreground;
        margin-left: 2;
    }

    .skill-trigger {
        color: $accent;
        margin-left: 2;
    }

    .skill-always-active {
        color: $success;
        text-style: italic;
    }

    .skills-no-skills {
        color: $warning;
        text-style: italic;
    }

    .skills-error {
        color: $error;
    }
"""
