"""Tests for SingleLineInputWithWrapping widget."""

import pytest
from textual.app import App
from textual.events import Paste

from openhands_cli.tui.widgets.user_input.single_line_input import (
    SingleLineInputWithWrapping,
)


class SingleLineInputTestApp(App):
    """Test app for SingleLineInputWithWrapping."""

    def compose(self):
        yield SingleLineInputWithWrapping(placeholder="Test placeholder")


class TestSingleLineInputWithWrapping:
    """Tests for SingleLineInputWithWrapping widget."""

    @pytest.mark.asyncio
    async def test_enter_key_posts_enter_pressed_message(self) -> None:
        """Pressing Enter emits EnterPressed message instead of inserting newline."""
        app = SingleLineInputTestApp()
        messages_received = []

        async with app.run_test() as pilot:
            widget = app.query_one(SingleLineInputWithWrapping)

            # Capture messages
            original_post_message = widget.post_message

            def capture_message(message):
                messages_received.append(message)
                return original_post_message(message)

            widget.post_message = capture_message

            # Type some text first
            widget.text = "Hello"
            widget.focus()
            await pilot.pause()

            # Press Enter
            await pilot.press("enter")
            await pilot.pause()

            # Check that EnterPressed message was posted
            enter_messages = [
                m
                for m in messages_received
                if isinstance(m, SingleLineInputWithWrapping.EnterPressed)
            ]
            assert len(enter_messages) == 1

    @pytest.mark.asyncio
    async def test_enter_key_prevents_newline_insertion(self) -> None:
        """After Enter, the text should not contain a newline character."""
        app = SingleLineInputTestApp()

        async with app.run_test() as pilot:
            widget = app.query_one(SingleLineInputWithWrapping)

            # Set initial text
            widget.text = "Hello"
            widget.focus()
            await pilot.pause()

            # Press Enter
            await pilot.press("enter")
            await pilot.pause()

            # Verify no newline was inserted
            assert "\n" not in widget.text
            assert widget.text == "Hello"

    @pytest.mark.asyncio
    async def test_multiline_paste_posts_message(self) -> None:
        """Pasting multi-line content triggers MultiLinePasteDetected message."""
        app = SingleLineInputTestApp()
        messages_received = []

        async with app.run_test() as pilot:
            widget = app.query_one(SingleLineInputWithWrapping)

            # Capture messages
            original_post_message = widget.post_message

            def capture_message(message):
                messages_received.append(message)
                return original_post_message(message)

            widget.post_message = capture_message

            widget.focus()
            await pilot.pause()

            # Simulate multi-line paste
            paste_event = Paste(text="Line 1\nLine 2")
            widget.post_message(paste_event)
            await pilot.pause()

            # Check that MultiLinePasteDetected was posted
            paste_messages = [
                m
                for m in messages_received
                if isinstance(m, SingleLineInputWithWrapping.MultiLinePasteDetected)
            ]
            assert len(paste_messages) == 1
            assert paste_messages[0].text == "Line 1\nLine 2"

    @pytest.mark.asyncio
    async def test_single_line_paste_handled_normally(self) -> None:
        """Single-line paste does NOT trigger the detection message."""
        app = SingleLineInputTestApp()
        messages_received = []

        async with app.run_test() as pilot:
            widget = app.query_one(SingleLineInputWithWrapping)

            # Capture messages
            original_post_message = widget.post_message

            def capture_message(message):
                messages_received.append(message)
                return original_post_message(message)

            widget.post_message = capture_message

            widget.focus()
            await pilot.pause()

            # Simulate single-line paste
            paste_event = Paste(text="Single line text")
            widget.post_message(paste_event)
            await pilot.pause()

            # Check that MultiLinePasteDetected was NOT posted
            paste_messages = [
                m
                for m in messages_received
                if isinstance(m, SingleLineInputWithWrapping.MultiLinePasteDetected)
            ]
            assert len(paste_messages) == 0

    @pytest.mark.asyncio
    async def test_placeholder_is_set_on_mount(self) -> None:
        """Placeholder text is properly set after mounting."""
        app = SingleLineInputTestApp()

        async with app.run_test() as pilot:
            widget = app.query_one(SingleLineInputWithWrapping)
            await pilot.pause()

            # Check placeholder was set
            assert widget.placeholder is not None
            # The placeholder should contain "Test placeholder"
            assert "Test placeholder" in str(widget.placeholder)
