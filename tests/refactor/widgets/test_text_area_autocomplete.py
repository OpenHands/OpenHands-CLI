"""Tests for TextAreaAutoComplete widget functionality."""

from unittest import mock

import pytest

from openhands_cli.refactor.widgets.user_input.models import (
    CompletionItem,
    CompletionType,
)
from openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete import (
    TextAreaAutoComplete,
    detect_completion_type,
)


class TestDetectCompletionType:
    """Tests for the detect_completion_type function."""

    @pytest.mark.parametrize(
        "text,expected_type",
        [
            # Command completion
            ("/", CompletionType.COMMAND),
            ("/h", CompletionType.COMMAND),
            ("/help", CompletionType.COMMAND),
            ("  /help", CompletionType.COMMAND),  # Leading whitespace
            # Command with space ends completion
            ("/help ", CompletionType.NONE),
            ("/help arg", CompletionType.NONE),
            # File completion
            ("@", CompletionType.FILE),
            ("@R", CompletionType.FILE),
            ("@README", CompletionType.FILE),
            ("read @", CompletionType.FILE),
            ("read @R", CompletionType.FILE),
            ("@src/", CompletionType.FILE),
            # File with space after path ends completion
            ("@file ", CompletionType.NONE),
            ("read @file ", CompletionType.NONE),
            # No completion
            ("", CompletionType.NONE),
            ("hello", CompletionType.NONE),
            ("hello world", CompletionType.NONE),
        ],
    )
    def test_detect_completion_type(self, text, expected_type):
        """detect_completion_type correctly identifies completion context."""
        assert detect_completion_type(text) == expected_type


class TestTextAreaAutoComplete:
    """Tests for the TextAreaAutoComplete behavior (commands + file paths)."""

    @pytest.fixture
    def autocomplete(self):
        """Create an autocomplete instance."""
        return TextAreaAutoComplete(command_candidates=[])

    # Command candidate logic

    @pytest.mark.parametrize(
        "text,expected_count",
        [
            ("/", 3),  # Should show all commands
            ("/h", 1),  # Should filter to /help
            ("/help", 1),  # Should filter to /help
            ("/e", 1),  # Should filter to /exit
            ("/c", 1),  # Should filter to /clear
            ("/x", 0),  # No match
            ("/help ", 0),  # Space ends command completion (via detect_completion_type)
        ],
    )
    def test_get_command_candidates_filters_correctly(self, text, expected_count):
        """_get_command_candidates returns filtered candidates for slash commands."""
        # Create command candidates similar to what COMMANDS provides
        command_candidates = []
        for cmd_text in [
            "/help - Display help",
            "/exit - Exit the application",
            "/clear - Clear the screen",
        ]:
            cmd = mock.MagicMock()
            cmd.main = mock.MagicMock()
            cmd.main.plain = cmd_text
            command_candidates.append(cmd)

        autocomplete = TextAreaAutoComplete(command_candidates=command_candidates)

        # Note: _get_command_candidates doesn't check for spaces - that's done
        # in update_candidates. So we need to only test valid command prefixes.
        if " " not in text:
            candidates = autocomplete._get_command_candidates(text)
            assert len(candidates) == expected_count
            # Verify all candidates are CompletionItem
            for c in candidates:
                assert isinstance(c, CompletionItem)
                assert c.completion_type == CompletionType.COMMAND

    def test_command_candidates_have_correct_structure(self):
        """Command candidates have display_text, completion_value, and type."""
        cmd = mock.MagicMock()
        cmd.main = mock.MagicMock()
        cmd.main.plain = "/help - Display help"

        autocomplete = TextAreaAutoComplete(command_candidates=[cmd])
        candidates = autocomplete._get_command_candidates("/h")

        assert len(candidates) == 1
        item = candidates[0]
        assert item.display_text == "/help - Display help"
        assert item.completion_value == "/help"
        assert item.completion_type == CompletionType.COMMAND

    # File candidate logic

    def test_file_candidates_use_work_dir_and_add_prefixes(self, tmp_path, monkeypatch):
        """File candidates come from WORK_DIR, add @ prefix and 📁/📄 icons."""
        (tmp_path / "README.md").write_text("test")
        (tmp_path / "src").mkdir()

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(command_candidates=[])
        candidates = autocomplete._get_file_candidates("@")

        # Verify we got candidates
        assert len(candidates) == 2

        # Check structure
        display_texts = [c.display_text for c in candidates]
        completion_values = [c.completion_value for c in candidates]

        assert any("README.md" in d for d in display_texts)
        assert any("src/" in d for d in display_texts)
        assert "@README.md" in completion_values
        assert "@src/" in completion_values

        # Verify all are FILE type
        for c in candidates:
            assert c.completion_type == CompletionType.FILE

    def test_file_candidates_for_nonexistent_directory(self, tmp_path, monkeypatch):
        """Non-existent directories produce no file candidates."""
        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(command_candidates=[])
        candidates = autocomplete._get_file_candidates("@nonexistent/")

        assert candidates == []

    def test_file_candidates_filters_by_filename(self, tmp_path, monkeypatch):
        """File candidates are filtered by the filename part after @."""
        (tmp_path / "README.md").write_text("test")
        (tmp_path / "requirements.txt").write_text("test")
        (tmp_path / "setup.py").write_text("test")

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(command_candidates=[])
        candidates = autocomplete._get_file_candidates("@R")
        display_texts = [c.display_text for c in candidates]

        # Should match README.md and requirements.txt (both start with R)
        assert any("README.md" in d for d in display_texts)
        assert any("requirements.txt" in d for d in display_texts)
        assert not any("setup.py" in d for d in display_texts)

    def test_file_candidates_handles_subdirectories(self, tmp_path, monkeypatch):
        """File candidates work with subdirectory paths."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("test")
        (src_dir / "utils.py").write_text("test")

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(command_candidates=[])
        candidates = autocomplete._get_file_candidates("@src/")
        display_texts = [c.display_text for c in candidates]

        assert any("main.py" in d for d in display_texts)
        assert any("utils.py" in d for d in display_texts)

    def test_file_candidates_skips_hidden_files_by_default(self, tmp_path, monkeypatch):
        """Hidden files are skipped unless explicitly typing them."""
        (tmp_path / ".hidden").write_text("test")
        (tmp_path / "visible.txt").write_text("test")

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(command_candidates=[])
        candidates = autocomplete._get_file_candidates("@")
        display_texts = [c.display_text for c in candidates]

        assert any("visible.txt" in d for d in display_texts)
        assert not any(".hidden" in d for d in display_texts)

    def test_file_candidates_shows_hidden_files_when_typing_dot(
        self, tmp_path, monkeypatch
    ):
        """Hidden files are shown when explicitly typing a dot."""
        (tmp_path / ".hidden").write_text("test")
        (tmp_path / "visible.txt").write_text("test")

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(command_candidates=[])
        candidates = autocomplete._get_file_candidates("@.")
        display_texts = [c.display_text for c in candidates]

        assert any(".hidden" in d for d in display_texts)

    def test_file_candidates_handles_permission_error(self, tmp_path, monkeypatch):
        """File candidates gracefully handle permission errors."""
        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(command_candidates=[])

        with mock.patch("pathlib.Path.iterdir", side_effect=PermissionError):
            candidates = autocomplete._get_file_candidates("@")

        assert candidates == []

    # Dropdown visibility behavior

    def test_show_dropdown_displays_candidates(self, autocomplete):
        """show_dropdown makes the dropdown visible with candidates."""
        items = [
            CompletionItem(
                display_text="test1",
                completion_value="test1",
                completion_type=CompletionType.COMMAND,
            ),
            CompletionItem(
                display_text="test2",
                completion_value="test2",
                completion_type=CompletionType.COMMAND,
            ),
        ]

        mock_option_list = mock.MagicMock()
        with mock.patch.object(
            autocomplete, "query_one", return_value=mock_option_list
        ):
            autocomplete.show_dropdown(items)

        assert autocomplete.display is True
        assert autocomplete._completion_items == items

    def test_show_dropdown_with_empty_candidates_hides(self, autocomplete):
        """show_dropdown with empty candidates hides the dropdown."""
        autocomplete.display = True

        with mock.patch.object(autocomplete, "hide_dropdown") as mock_hide:
            autocomplete.show_dropdown([])
            mock_hide.assert_called_once()

    def test_hide_dropdown_clears_state(self, autocomplete):
        """hide_dropdown hides dropdown and clears state."""
        autocomplete.display = True
        autocomplete._current_completion_type = CompletionType.COMMAND
        autocomplete._completion_items = [
            CompletionItem(
                display_text="test",
                completion_value="test",
                completion_type=CompletionType.COMMAND,
            )
        ]

        autocomplete.hide_dropdown()

        assert autocomplete.display is False
        assert autocomplete._current_completion_type == CompletionType.NONE
        assert autocomplete._completion_items == []

    def test_is_visible_returns_display_state(self, autocomplete):
        """is_visible returns the display property value."""
        # Note: Widget's default display is True, but CSS sets it to none
        # In tests without CSS, display defaults to True
        # So we explicitly set it to False to test the behavior
        autocomplete.display = False
        assert autocomplete.is_visible is False

        autocomplete.display = True
        assert autocomplete.is_visible is True

    def test_select_highlighted_returns_none_when_not_visible(self, autocomplete):
        """select_highlighted returns None when dropdown is not visible."""
        autocomplete.display = False

        result = autocomplete.select_highlighted()

        assert result is None

    def test_select_highlighted_returns_completion_item(self, autocomplete):
        """select_highlighted returns the highlighted CompletionItem."""
        item = CompletionItem(
            display_text="/help - Display help",
            completion_value="/help",
            completion_type=CompletionType.COMMAND,
        )
        autocomplete.display = True
        autocomplete._completion_items = [item]

        mock_option_list = mock.MagicMock()
        mock_option_list.highlighted = 0

        with mock.patch.object(
            type(autocomplete), "option_list", new_callable=mock.PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_option_list
            result = autocomplete.select_highlighted()

        assert result == item
        assert autocomplete.display is False

    def test_move_highlight_does_nothing_when_not_visible(self, autocomplete):
        """move_highlight does nothing when dropdown is not visible."""
        autocomplete.display = False

        mock_option_list = mock.MagicMock()
        with mock.patch.object(
            type(autocomplete), "option_list", new_callable=mock.PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_option_list
            autocomplete.move_highlight(1)

        mock_option_list.action_cursor_down.assert_not_called()
        mock_option_list.action_cursor_up.assert_not_called()

    def test_move_highlight_moves_cursor_down(self, autocomplete):
        """move_highlight with positive direction moves cursor down."""
        autocomplete.display = True

        mock_option_list = mock.MagicMock()
        with mock.patch.object(
            type(autocomplete), "option_list", new_callable=mock.PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_option_list
            autocomplete.move_highlight(1)

        mock_option_list.action_cursor_down.assert_called_once()

    def test_move_highlight_moves_cursor_up(self, autocomplete):
        """move_highlight with negative direction moves cursor up."""
        autocomplete.display = True

        mock_option_list = mock.MagicMock()
        with mock.patch.object(
            type(autocomplete), "option_list", new_callable=mock.PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_option_list
            autocomplete.move_highlight(-1)

        mock_option_list.action_cursor_up.assert_called_once()

    # process_key tests

    def test_process_key_returns_false_when_not_visible(self, autocomplete):
        """process_key returns False when dropdown is not visible."""
        autocomplete.display = False

        assert autocomplete.process_key("down") is False
        assert autocomplete.process_key("up") is False
        assert autocomplete.process_key("tab") is False
        assert autocomplete.process_key("enter") is False
        assert autocomplete.process_key("escape") is False

    def test_process_key_down_moves_highlight(self, autocomplete):
        """process_key 'down' moves highlight down."""
        autocomplete.display = True

        with mock.patch.object(autocomplete, "move_highlight") as mock_move:
            result = autocomplete.process_key("down")

        assert result is True
        mock_move.assert_called_once_with(1)

    def test_process_key_up_moves_highlight(self, autocomplete):
        """process_key 'up' moves highlight up."""
        autocomplete.display = True

        with mock.patch.object(autocomplete, "move_highlight") as mock_move:
            result = autocomplete.process_key("up")

        assert result is True
        mock_move.assert_called_once_with(-1)

    def test_process_key_escape_hides_dropdown(self, autocomplete):
        """process_key 'escape' hides the dropdown."""
        autocomplete.display = True

        with mock.patch.object(autocomplete, "hide_dropdown") as mock_hide:
            result = autocomplete.process_key("escape")

        assert result is True
        mock_hide.assert_called_once()

    def test_process_key_tab_selects_and_posts_message(self, autocomplete):
        """process_key 'tab' selects highlighted and posts message."""
        item = CompletionItem(
            display_text="test",
            completion_value="test",
            completion_type=CompletionType.COMMAND,
        )
        autocomplete.display = True

        with (
            mock.patch.object(autocomplete, "select_highlighted", return_value=item),
            mock.patch.object(autocomplete, "post_message") as mock_post,
        ):
            result = autocomplete.process_key("tab")

        assert result is True
        mock_post.assert_called_once()
        message = mock_post.call_args[0][0]
        assert isinstance(message, TextAreaAutoComplete.CompletionSelected)
        assert message.item == item

    def test_process_key_enter_selects_and_posts_message(self, autocomplete):
        """process_key 'enter' selects highlighted and posts message."""
        item = CompletionItem(
            display_text="test",
            completion_value="test",
            completion_type=CompletionType.COMMAND,
        )
        autocomplete.display = True

        with (
            mock.patch.object(autocomplete, "select_highlighted", return_value=item),
            mock.patch.object(autocomplete, "post_message") as mock_post,
        ):
            result = autocomplete.process_key("enter")

        assert result is True
        mock_post.assert_called_once()

    # update_candidates tests

    def test_update_candidates_routes_to_command(self, autocomplete):
        """update_candidates calls _get_command_candidates for / prefix."""
        with (
            mock.patch.object(
                autocomplete, "_get_command_candidates", return_value=[]
            ) as mock_cmd,
            mock.patch.object(
                autocomplete, "_get_file_candidates", return_value=[]
            ) as mock_file,
            mock.patch.object(autocomplete, "hide_dropdown"),
        ):
            autocomplete.update_candidates("/help")

        mock_cmd.assert_called_once_with("/help")
        mock_file.assert_not_called()

    def test_update_candidates_routes_to_file(self, autocomplete):
        """update_candidates calls _get_file_candidates for @ prefix."""
        with (
            mock.patch.object(
                autocomplete, "_get_command_candidates", return_value=[]
            ) as mock_cmd,
            mock.patch.object(
                autocomplete, "_get_file_candidates", return_value=[]
            ) as mock_file,
            mock.patch.object(autocomplete, "hide_dropdown"),
        ):
            autocomplete.update_candidates("@README")

        mock_file.assert_called_once_with("@README")
        mock_cmd.assert_not_called()

    def test_update_candidates_shows_dropdown_for_valid_candidates(
        self, tmp_path, monkeypatch
    ):
        """update_candidates shows dropdown when candidates are found."""
        (tmp_path / "test.txt").write_text("test")

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(command_candidates=[])

        with mock.patch.object(autocomplete, "show_dropdown") as mock_show:
            autocomplete.update_candidates("@t")
            mock_show.assert_called_once()
            args = mock_show.call_args[0][0]
            assert len(args) > 0
            assert all(isinstance(c, CompletionItem) for c in args)

    def test_update_candidates_hides_dropdown_for_no_candidates(self, autocomplete):
        """update_candidates hides dropdown when no candidates are found."""
        with mock.patch.object(autocomplete, "hide_dropdown") as mock_hide:
            autocomplete.update_candidates("no match here")
            mock_hide.assert_called_once()

    def test_update_candidates_sets_completion_type(self, autocomplete):
        """update_candidates sets the current_completion_type."""
        with (
            mock.patch.object(autocomplete, "_get_command_candidates", return_value=[]),
            mock.patch.object(autocomplete, "hide_dropdown"),
        ):
            autocomplete.update_candidates("/help")

        assert autocomplete._current_completion_type == CompletionType.COMMAND
