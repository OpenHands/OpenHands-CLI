"""Snapshot tests for CriticFeedbackWidget.

These tests help visualize and iterate on the button styling.

To update snapshots when intentional changes are made:
    pytest tests/snapshots/test_critic_feedback_snapshots.py --snapshot-update

To run these tests:
    pytest tests/snapshots/test_critic_feedback_snapshots.py
"""

from typing import ClassVar
from unittest.mock import MagicMock

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Footer, Static

from openhands_cli.theme import OPENHANDS_THEME


def _create_mock_critic_result(score: float = 0.65, success: bool = True):
    """Create a mock CriticResult for testing."""
    mock_result = MagicMock()
    mock_result.score = score
    mock_result.success = success
    mock_result.metadata = {"event_ids": ["test-event-1"]}
    return mock_result


class MockCriticFeedbackWidget(Static, can_focus=True):
    """Mock widget that replicates the CriticFeedbackWidget styling for testing."""

    DEFAULT_CSS = """
    MockCriticFeedbackWidget {
        height: auto;
        background: transparent;
        color: $foreground;
        padding: 0 1;
        margin: 1 0;
    }

    MockCriticFeedbackWidget Horizontal {
        height: auto;
        width: 100%;
        margin-top: 1;
    }

    MockCriticFeedbackWidget Button {
        width: 12;
        margin-right: 1;
        border: none;
        background: $surface-darken-1;
        color: $foreground;
    }

    MockCriticFeedbackWidget Button:hover {
        background: $surface-lighten-1;
    }
    """

    BUTTON_LABELS: ClassVar[dict[str, str]] = {
        "accurate": "[1] Accurate",
        "too_high": "[2] Too high",
        "too_low": "[3] Too low",
        "not_applicable": "[4] N/A",
        "dismiss": "[0] Dismiss",
    }

    def compose(self):
        """Compose the widget with prompt and buttons."""
        yield Static(
            "[bold]Does the critic's success prediction align with your "
            "perception?[/bold]",
            id="feedback-prompt",
        )
        with Horizontal():
            yield Button(
                self.BUTTON_LABELS["accurate"], id="btn-accurate", compact=True
            )
            yield Button(
                self.BUTTON_LABELS["too_high"], id="btn-too_high", compact=True
            )
            yield Button(self.BUTTON_LABELS["too_low"], id="btn-too_low", compact=True)
            yield Button(
                self.BUTTON_LABELS["not_applicable"],
                id="btn-not_applicable",
                compact=True,
            )
            yield Button(self.BUTTON_LABELS["dismiss"], id="btn-dismiss", compact=True)


class TestCriticFeedbackWidgetSnapshots:
    """Snapshot tests for the CriticFeedbackWidget."""

    def test_critic_feedback_widget_display(self, snap_compare):
        """Snapshot test for critic feedback widget with buttons."""

        class CriticFeedbackTestApp(App):
            CSS = """
            Screen {
                background: $background;
            }
            #content {
                width: 100%;
                height: auto;
                padding: 1;
            }
            """

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.register_theme(OPENHANDS_THEME)
                self.theme = OPENHANDS_THEME.name

            def compose(self) -> ComposeResult:
                yield Static(
                    "Sample conversation content above the widget", id="content"
                )
                yield MockCriticFeedbackWidget()
                yield Footer()

        assert snap_compare(
            CriticFeedbackTestApp(),
            terminal_size=(100, 20),
        )
