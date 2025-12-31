"""High-impact tests for autocomplete functionality and command handling."""

from unittest import mock

import pytest
from textual.widgets import Input
from textual_autocomplete import TargetState

from openhands_cli.tui.widgets.autocomplete import EnhancedAutoComplete


class TestEnhancedAutoComplete:
    """Tests for the enhanced autocomplete behavior (commands + file paths)."""

    #
    # Search-string logic
    #

    @pytest.mark.parametrize(
        "text,cursor_position,expected",
        [
            # Command search strings
            ("/", 1, "/"),
            ("/h", 2, "/h"),
            ("/help", 5, "/help"),
            ("/help ", 6, ""),  # space ends command completion
            # File path search strings - @ at beginning
            ("@", 1, ""),  # empty filename part
            ("@R", 2, "R"),
            ("@README", 7, "README"),
            ("@openhands_cli/", 15, ""),  # directory, no filename yet
            ("@openhands_cli/test", 19, "test"),
            ("@path/to/file.py", 16, "file.py"),
            ("@file ", 6, ""),  # space stops file completion
            # File path search strings - @ anywhere in text
            ("read @", 6, ""),  # empty filename part
            ("read @R", 7, "R"),
            ("cat @README", 11, "README"),
            ("edit @src/main.py", 17, "main.py"),
            ("open @openhands_cli/", 20, ""),  # directory only
            ("view @file ", 11, ""),  # space stops completion
            # Two @-paths on the same line: should use the last one
            ("open @README and @REA", len("open @README and @REA"), "REA"),
            # @ not at end of string, cursor right after @
            # Cursor is just after '@', even though more text follows later.
            (
                "read @ and more",
                len("read @"),
                "",
            ),  # empty filename, still triggers file mode
            (
                "read @R and more",
                len("read @R"),
                "R",
            ),  # filename "R" before rest of text
            (
                "edit @src/main.py rest",
                len("edit @src/main.py"),
                "main.py",
            ),  # ignores trailing " rest"
            # No completion cases
            ("hello", 5, ""),
            ("", 0, ""),
            # No completion cases
            ("hello", 5, ""),
            ("", 0, ""),
        ],
    )
    def test_get_search_string_for_commands_and_files(
        self, text, cursor_position, expected
    ):
        """get_search_string handles /-commands and @-file paths correctly."""
        mock_input = mock.MagicMock(spec=Input)
        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=[])

        state = TargetState(text=text, cursor_position=cursor_position)
        result = autocomplete.get_search_string(state)

        assert result == expected

    #
    # Candidate routing logic
    #

    @pytest.mark.parametrize(
        "text,cursor_position,expected_route",
        [
            ("/", 1, "command"),
            ("/he", 3, "command"),
            ("@", 1, "file"),
            ("read @R", 7, "file"),
            ("hello", 5, "none"),
            ("", 0, "none"),
            ("read @ and more", len("read @"), "file"),
        ],
    )
    def test_get_candidates_routes_to_command_or_file_helpers(
        self, text, cursor_position, expected_route
    ):
        """get_candidates chooses the right helper based on context."""
        mock_input = mock.MagicMock(spec=Input)
        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=[])

        state = TargetState(text=text, cursor_position=cursor_position)

        with (
            mock.patch.object(
                autocomplete, "_get_command_candidates", return_value=["CMD"]
            ) as mock_cmd,
            mock.patch.object(
                autocomplete, "_get_file_candidates", return_value=["FILE"]
            ) as mock_file,
        ):
            result = autocomplete.get_candidates(state)

        if expected_route == "command":
            mock_cmd.assert_called_once()
            mock_file.assert_not_called()
            assert result == ["CMD"]
        elif expected_route == "file":
            mock_file.assert_called_once()
            mock_cmd.assert_not_called()
            assert result == ["FILE"]
        else:
            mock_cmd.assert_not_called()
            mock_file.assert_not_called()
            assert result == []

    #
    # File candidates: filesystem behavior (using tmp_path)
    #

    def test_file_candidates_use_work_dir_and_add_prefixes(self, tmp_path, monkeypatch):
        """File candidates come from WORK_DIR, add @ prefix and 📁/📄 icons."""
        # Create a temporary WORK_DIR with one file and one directory
        (tmp_path / "README.md").write_text("test")
        (tmp_path / "src").mkdir()

        # Patch WORK_DIR in the autocomplete module to our tmp_path
        monkeypatch.setattr(
            "openhands_cli.tui.widgets.autocomplete.WORK_DIR",
            str(tmp_path),
        )

        mock_input = mock.MagicMock(spec=Input)
        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=[])

        state = TargetState(text="@", cursor_position=1)
        candidates = autocomplete.get_candidates(state)

        # We should get candidates for both README.md and src/
        names = [str(c.main) for c in candidates]
        assert "@README.md" in names
        assert "@src/" in names

        # And prefixes should be either 📁 (dir) or 📄 (file)
        assert all(
            hasattr(c, "prefix") and c.prefix in ["📁", "📄"] for c in candidates
        )

    def test_file_candidates_for_nonexistent_directory_returns_empty_list(
        self, monkeypatch, tmp_path
    ):
        """Non-existent directories produce no file candidates."""
        # Point WORK_DIR at a real dir, but use a path that does not exist inside it.
        monkeypatch.setattr(
            "openhands_cli.tui.widgets.autocomplete.WORK_DIR",
            str(tmp_path),
        )

        mock_input = mock.MagicMock(spec=Input)
        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=[])

        state = TargetState(text="@nonexistent/", cursor_position=len("@nonexistent/"))
        candidates = autocomplete.get_candidates(state)

        assert candidates == []

    #
    # Completion application
    #

    @pytest.mark.parametrize(
        "initial_value,cursor_pos,completion_value,expected_insert",
        [
            # Command completions: only the command part should be inserted
            ("/he", 3, "/help - Display available commands", "/help"),
            ("/ex", 3, "/exit", "/exit"),
            # File completions: @ at start of input
            ("@READ", 5, "@README.md", "@README.md"),
            # File completions: @ in the middle of the text, keep prefix
            ("read @READ", 10, "@README.md", "read @README.md"),
            # File completions: last @ wins
            (
                "open @README and @REA",
                len("open @README and @REA"),
                "@README.md",
                "open @README and @README.md",
            ),
        ],
    )
    def test_apply_completion_inserts_expected_text(
        self,
        initial_value,
        cursor_pos,
        completion_value,
        expected_insert,
    ):
        """apply_completion clears the input and inserts the expected completed text."""
        mock_input = mock.MagicMock(spec=Input)
        mock_input.value = initial_value

        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=[])

        # TargetState.text is always the input up to the cursor
        state = TargetState(text=initial_value, cursor_position=cursor_pos)

        autocomplete.apply_completion(completion_value, state)

        # apply_completion always clears the target value first
        assert mock_input.value == ""
        mock_input.insert_text_at_cursor.assert_called_once_with(expected_insert)

    #
    # Dropdown visibility behavior
    #

    def test_should_show_dropdown_behavior(self, monkeypatch):
        """Dropdown visibility logic depends on option_count and search_string."""
        mock_input = mock.MagicMock(spec=Input)
        autocomplete = EnhancedAutoComplete(mock_input, command_candidates=[])

        # Helper option class
        class DummyOption:
            def __init__(self, prompt):
                self.prompt = prompt

        # Create a fake option_list container we will swap in and out
        option_list = mock.MagicMock()
        # Patch the property so autocomplete.option_list returns our mock
        monkeypatch.setattr(
            autocomplete.__class__,
            "option_list",
            property(lambda self: option_list),
        )

        #
        # Case 1: no options → False
        #
        option_list.option_count = 0
        assert autocomplete.should_show_dropdown(search_string="") is False

        #
        # Case 2: one option exactly equal to search_string → False
        #
        option_list.option_count = 1
        option_list.get_option_at_index.return_value = DummyOption(prompt="foo")
        assert autocomplete.should_show_dropdown(search_string="foo") is False

        #
        # Case 3: one option different from search_string → True
        #
        assert autocomplete.should_show_dropdown(search_string="bar") is True

        #
        # Case 4: multiple options → True regardless of search_string
        #
        option_list.option_count = 2
        assert autocomplete.should_show_dropdown(search_string="anything") is True
