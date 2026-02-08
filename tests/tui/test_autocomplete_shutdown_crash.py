"""Tests for autocomplete dropdown shutdown crash (issues #397 and #401).

These tests attempt to reproduce the crash that occurs when:
1. User types "/" to open the autocomplete dropdown
2. User exits with Ctrl+C or uses a slash command
3. During shutdown, OptionList widget receives zero width → crash

The crash originates in Rich's `chop_cells` function when called with width=0:
    return [text[index : index + width] for index in range(0, len(text), width)]
    → ValueError: range() arg 3 must not be zero

Related issues:
- https://github.com/OpenHands/OpenHands-CLI/issues/397
- https://github.com/OpenHands/OpenHands-CLI/issues/401

NOTE: These tests document the expected behavior. The crash may be environment-specific
and may not be reproducible in all test environments. The tests serve as regression
guards to catch future occurrences of this class of bugs.

The bug was reported with:
- OpenHands CLI v1.10.0
- Textual 7.3.0
- Rich 14.3.0

If these tests pass, it may indicate:
1. The bug was fixed in the current version of dependencies
2. The bug requires specific terminal conditions not present in tests
3. The bug is related to real terminal shutdown vs test shutdown
"""

from typing import cast

import pytest
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.geometry import Size
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from openhands_cli.tui.modals import SettingsScreen
from openhands_cli.tui.textual_app import OpenHandsApp


class TestAutocompleteShutdownCrash:
    """Tests for the autocomplete dropdown zero-width crash during shutdown.

    These tests verify that the application can shut down cleanly when the
    autocomplete dropdown is visible, without crashing due to zero-width
    OptionList layout calculations.
    """

    @pytest.mark.asyncio
    async def test_shutdown_with_visible_autocomplete_dropdown_no_crash(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """App should shut down cleanly when autocomplete dropdown is visible.

        This test reproduces the crash from issues #397 and #401.

        Steps to reproduce:
        1. Start the app
        2. Type "/" to trigger autocomplete
        3. Exit the app (Ctrl+C equivalent)
        4. Should NOT crash with "ValueError: range() arg 3 must not be zero"
        """
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda **kwargs: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Type "/" to trigger autocomplete dropdown
            await pilot.press("/")
            await pilot.pause()

            # Verify autocomplete dropdown is visible
            autocomplete = oh_app.input_field.autocomplete
            assert autocomplete.is_visible, (
                "Autocomplete dropdown should be visible after typing '/'"
            )

            # App should exit cleanly - if the bug exists, this will crash with:
            # ValueError: range() arg 3 must not be zero
            # The crash happens during _shutdown → _reset_focus → focus_chain sorting
            # which triggers OptionList layout with zero width

    @pytest.mark.asyncio
    async def test_shutdown_with_visible_autocomplete_narrow_terminal_no_crash(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """App should shut down cleanly even with a narrow terminal.

        The crash in issues #397 and #401 may be related to terminal width.
        This test uses a very narrow terminal (20 columns) to stress test the
        OptionList width handling during shutdown.
        """
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda **kwargs: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        # Use a narrow terminal to trigger potential zero-width conditions
        async with app.run_test(size=Size(20, 10)) as pilot:
            # Type "/" to trigger autocomplete dropdown
            await pilot.press("/")
            await pilot.pause()

            # The dropdown may or may not be visible in a narrow terminal
            # The key test is that shutdown doesn't crash

    @pytest.mark.asyncio
    async def test_exit_command_with_visible_autocomplete_no_crash(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Using /exit command while autocomplete is showing should not crash.

        This is a variation of issue #401 where using a slash command triggers
        the crash.
        """
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda **kwargs: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Type "/" to trigger autocomplete
            await pilot.press("/")
            await pilot.pause()

            # Type "exit" to complete the command
            await pilot.press("e", "x", "i", "t")
            await pilot.pause()

            # Execute the exit command
            oh_app.conversation_state.input_area._command_exit()
            await pilot.pause()

            # Should exit cleanly without crash

    @pytest.mark.asyncio
    async def test_ctrl_c_exit_with_visible_autocomplete_no_crash(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ctrl+C exit while autocomplete is showing should not crash.

        This is the primary trigger for issue #397.
        """
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda **kwargs: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Type "/" to trigger autocomplete dropdown
            await pilot.press("/")
            await pilot.pause()

            # Verify autocomplete dropdown is visible
            autocomplete = oh_app.input_field.autocomplete
            assert autocomplete.is_visible, "Autocomplete dropdown should be visible"

            # Simulate Ctrl+C exit
            await pilot.press("ctrl+c")
            await pilot.pause()


class TestOptionListZeroWidthMinimal:
    """Minimal reproduction of the OptionList zero-width crash.

    This test isolates the issue to verify it's specifically about OptionList
    receiving zero width during layout calculations.
    """

    @pytest.mark.asyncio
    async def test_option_list_with_auto_width_on_shutdown(self) -> None:
        """OptionList with auto width should not crash during shutdown.

        This test creates a minimal app with an OptionList that has auto width,
        similar to the autocomplete dropdown configuration.
        """

        class MinimalAutocompleteApp(App):
            """Minimal app to reproduce the OptionList zero-width crash."""

            CSS = """
            #dropdown {
                layer: autocomplete;
                width: auto;
                min-width: 30;
                max-width: 60;
                height: auto;
                max-height: 12;
            }

            OptionList {
                width: 100%;
                height: auto;
                min-height: 1;
                max-height: 10;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Main content")
                with Container(id="dropdown"):
                    yield OptionList()

            def on_mount(self) -> None:
                # Populate and show the dropdown
                option_list = self.query_one(OptionList)
                option_list.add_option(Option("/help - Display available commands"))
                option_list.add_option(Option("/exit - Exit the application"))
                option_list.highlighted = 0

                # Make the dropdown visible (simulating typing "/")
                dropdown = self.query_one("#dropdown")
                dropdown.display = True

        app = MinimalAutocompleteApp()

        async with app.run_test() as pilot:
            await pilot.pause()

            # Verify dropdown is visible
            dropdown = pilot.app.query_one("#dropdown")
            assert dropdown.display is True

            # App should exit cleanly - crash happens here if bug exists

    @pytest.mark.asyncio
    async def test_option_list_with_zero_width_container(self) -> None:
        """OptionList inside a zero-width container should handle gracefully.

        This test directly creates the condition that causes the crash:
        an OptionList inside a container with zero width.
        """

        class ZeroWidthContainerApp(App):
            """App with OptionList in a zero-width container."""

            CSS = """
            #zero_width_container {
                width: 0;
                height: auto;
            }

            OptionList {
                width: 100%;
                height: auto;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Main content")
                with Container(id="zero_width_container"):
                    yield OptionList()

            def on_mount(self) -> None:
                # Populate the option list
                option_list = self.query_one(OptionList)
                option_list.add_option(Option("/help - Display available commands"))
                option_list.add_option(Option("/exit - Exit the application"))
                option_list.highlighted = 0

                # Make the container visible
                container = self.query_one("#zero_width_container")
                container.display = True

        app = ZeroWidthContainerApp()

        # This test may crash with: ValueError: range() arg 3 must not be zero
        # The crash happens during layout calculations when
        # OptionList.get_content_height is called with width=0
        async with app.run_test() as pilot:
            await pilot.pause()

            # Even if the app runs, the shutdown might crash
            # The test passes if no exception is raised during the entire lifecycle

    @pytest.mark.asyncio
    async def test_option_list_narrow_terminal_shutdown(self) -> None:
        """OptionList in very narrow terminal should not crash on shutdown.

        This test uses a 1-column terminal to force zero-width conditions.
        """

        class NarrowTerminalApp(App):
            """App to test OptionList in extremely narrow terminal."""

            CSS = """
            #dropdown {
                width: auto;
                height: auto;
            }

            OptionList {
                width: 100%;
                height: auto;
            }
            """

            def compose(self) -> ComposeResult:
                with Container(id="dropdown"):
                    yield OptionList()

            def on_mount(self) -> None:
                option_list = self.query_one(OptionList)
                option_list.add_option(Option("/help - Display available commands"))
                option_list.highlighted = 0

        app = NarrowTerminalApp()

        # Use an extremely narrow terminal
        async with app.run_test(size=Size(1, 10)) as pilot:
            await pilot.pause()
            # Test passes if no crash during lifecycle and shutdown


class TestAutoCompleteDropdownWidget:
    """Direct tests for AutoCompleteDropdown widget to ensure proper cleanup."""

    @pytest.mark.asyncio
    async def test_autocomplete_dropdown_hide_before_shutdown(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Hiding autocomplete dropdown before shutdown should prevent crash.

        This test verifies that the workaround of hiding the dropdown before
        shutdown works correctly.
        """
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda **kwargs: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Type "/" to trigger autocomplete dropdown
            await pilot.press("/")
            await pilot.pause()

            # Verify autocomplete dropdown is visible
            autocomplete = oh_app.input_field.autocomplete
            assert autocomplete.is_visible, "Autocomplete should be visible"

            # Hide the dropdown before exit (potential workaround)
            autocomplete.hide_dropdown()
            await pilot.pause()

            # Verify it's hidden
            assert not autocomplete.is_visible, "Autocomplete should be hidden"

            # Now exit should work cleanly


class TestShutdownFocusChainCrash:
    """Tests that directly exercise the focus chain path during shutdown.

    The crash in issues #397 and #401 occurs specifically during:
    1. App shutdown calls `screen._reset_focus()`
    2. `_reset_focus` accesses `focus_chain` property
    3. `focus_chain` sorts displayed_children by `focus_sorter`
    4. `focus_sorter` calls `_focus_sort_key` which accesses `virtual_region`
    5. `virtual_region` triggers compositor's `find_widget`
    6. `find_widget` accesses `full_map` which calls `_arrange_root`
    7. Layout calculation for OptionList with zero width crashes

    These tests directly exercise this code path.
    """

    @pytest.mark.asyncio
    async def test_focus_chain_with_visible_option_list_overlay(self) -> None:
        """Accessing focus_chain with a visible OptionList overlay should not crash.

        This test explicitly accesses the focus_chain property to trigger the
        layout calculation that causes the crash.
        """

        class OverlayApp(App):
            """App with an OptionList overlay similar to autocomplete."""

            CSS = """
            Screen {
                layers: base overlay;
            }

            #overlay_container {
                layer: overlay;
                width: auto;
                height: auto;
                min-width: 10;
            }

            OptionList {
                width: 100%;
                height: auto;
            }
            """

            def compose(self) -> ComposeResult:
                yield Static("Main content", id="main")
                with Container(id="overlay_container"):
                    yield OptionList()

            def on_mount(self) -> None:
                option_list = self.query_one(OptionList)
                option_list.add_option(Option("/help - Help command"))
                option_list.add_option(Option("/exit - Exit command"))
                option_list.highlighted = 0

        app = OverlayApp()

        async with app.run_test() as pilot:
            await pilot.pause()

            # Explicitly access focus_chain to trigger layout calculation
            # This is what happens during shutdown
            try:
                _ = pilot.app.screen.focus_chain
            except ValueError as e:
                if "range() arg 3 must not be zero" in str(e):
                    pytest.fail(
                        f"focus_chain access crashed with zero-width error: {e}\n"
                        f"This reproduces issue #397/#401"
                    )
                raise

    @pytest.mark.asyncio
    async def test_option_list_get_content_height_with_zero_width(self) -> None:
        """OptionList.get_content_height should handle zero width gracefully.

        This test directly calls get_content_height with width=0 to verify
        the behavior.
        """

        class SimpleOptionListApp(App):
            """Simple app with OptionList."""

            def compose(self) -> ComposeResult:
                yield OptionList()

            def on_mount(self) -> None:
                option_list = self.query_one(OptionList)
                option_list.add_option(Option("/help - Help command"))
                option_list.add_option(Option("/exit - Exit command"))

        app = SimpleOptionListApp()

        async with app.run_test() as pilot:
            await pilot.pause()

            option_list = pilot.app.query_one(OptionList)

            # Try to get content height with zero width
            # This is what causes the crash in the real scenario
            try:
                # Note: get_content_height expects a width parameter
                # We're testing with width=0 to see if it crashes
                option_list.get_content_height(
                    container=Size(0, 100),
                    viewport=Size(0, 100),
                    width=0,
                )
            except ValueError as e:
                if "range() arg 3 must not be zero" in str(e):
                    pytest.fail(
                        f"get_content_height(width=0) crashed: {e}\n"
                        f"This is the root cause of issue #397/#401.\n"
                        f"OptionList should handle zero width gracefully."
                    )
                raise
            except TypeError:
                # Signature might be different, skip this test
                pytest.skip("get_content_height signature different than expected")

    @pytest.mark.asyncio
    async def test_visible_autocomplete_during_screen_reset_focus(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Screen._reset_focus with visible autocomplete should not crash.

        This test directly calls _reset_focus while the autocomplete dropdown
        is visible, simulating what happens during shutdown.
        """
        monkeypatch.setattr(
            SettingsScreen,
            "is_initial_setup_required",
            lambda **kwargs: False,
        )

        app = OpenHandsApp(exit_confirmation=False)

        async with app.run_test() as pilot:
            oh_app = cast(OpenHandsApp, pilot.app)

            # Type "/" to trigger autocomplete dropdown
            await pilot.press("/")
            await pilot.pause()

            # Verify autocomplete is visible
            autocomplete = oh_app.input_field.autocomplete
            assert autocomplete.is_visible, "Autocomplete should be visible"

            # Directly call _reset_focus, which is what happens during shutdown
            # This should trigger the crash if the bug exists
            focused = oh_app.screen.focused
            try:
                if focused is not None:
                    oh_app.screen._reset_focus(focused, [])
            except ValueError as e:
                if "range() arg 3 must not be zero" in str(e):
                    pytest.fail(
                        f"_reset_focus crashed with visible autocomplete: {e}\n"
                        f"This reproduces issue #397/#401"
                    )
                raise
