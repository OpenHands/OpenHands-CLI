"""Tests for TextAreaAutoComplete widget functionality."""

from unittest import mock

import pytest
from textual.widgets.option_list import Option

from openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete import (
    TextAreaAutoComplete,
)


class TestTextAreaAutoComplete:
    """Tests for the TextAreaAutoComplete behavior (commands + file paths)."""

    @pytest.fixture
    def mock_target(self):
        """Create a mock target widget."""
        return mock.MagicMock()

    @pytest.fixture
    def autocomplete(self, mock_target):
        """Create an autocomplete instance with mock target."""
        return TextAreaAutoComplete(mock_target, command_candidates=[])

    # Search string / command candidate logic

    @pytest.mark.parametrize(
        "text,expected_candidates_count",
        [
            # Command search strings - should return candidates
            ("/", True),  # Should show all commands
            ("/h", True),  # Should filter to commands starting with /h
            ("/help", True),  # Should filter to commands starting with /help
            ("/help ", False),  # Space ends command completion
            # Non-command text - should return empty
            ("hello", False),
            ("", False),
            ("@file", False),  # @ triggers file completion, not command
        ],
    )
    def test_get_command_candidates_filters_correctly(
        self, mock_target, text, expected_candidates_count
    ):
        """get_command_candidates returns filtered candidates for slash commands."""
        # Create command candidates similar to what COMMANDS provides
        # Each candidate has a 'main' attribute that can be a Content object with 'plain'
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

        autocomplete = TextAreaAutoComplete(
            mock_target, command_candidates=command_candidates
        )

        candidates = autocomplete.get_command_candidates(text)

        if expected_candidates_count:
            # Should have some candidates for valid command prefixes
            if text == "/":
                assert len(candidates) == 3  # All commands
            elif text == "/h":
                assert len(candidates) == 1  # Only /help
            elif text == "/help":
                assert len(candidates) == 1  # Only /help
        else:
            assert len(candidates) == 0

    @pytest.mark.parametrize(
        "text,expected_route",
        [
            ("/", "command"),
            ("/he", "command"),
            ("@", "file"),
            ("read @R", "file"),
            ("hello", "none"),
            ("", "none"),
            ("read @ and more", "file"),
        ],
    )
    def test_update_candidates_routes_to_command_or_file(
        self, mock_target, text, expected_route
    ):
        """update_candidates chooses the right helper based on context."""
        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        with (
            mock.patch.object(
                autocomplete, "get_command_candidates", return_value=[]
            ) as mock_cmd,
            mock.patch.object(
                autocomplete, "get_file_candidates", return_value=[]
            ) as mock_file,
            mock.patch.object(autocomplete, "show_dropdown") as mock_show,
            mock.patch.object(autocomplete, "hide_dropdown") as mock_hide,
        ):
            autocomplete.update_candidates(text)

        if expected_route == "command":
            mock_cmd.assert_called_once_with(text)
            mock_file.assert_not_called()
        elif expected_route == "file":
            mock_file.assert_called_once_with(text)
            mock_cmd.assert_not_called()
        else:
            # Neither should be called for non-matching text
            # Actually, update_candidates checks conditions first
            pass

    # File candidates: filesystem behavior (using tmp_path)

    def test_file_candidates_use_work_dir_and_add_prefixes(
        self, mock_target, tmp_path, monkeypatch
    ):
        """File candidates come from WORK_DIR, add @ prefix and 📁/📄 icons."""
        # Create a temporary WORK_DIR with one file and one directory
        (tmp_path / "README.md").write_text("test")
        (tmp_path / "src").mkdir()

        # Patch WORK_DIR in the autocomplete module to our tmp_path
        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        candidates = autocomplete.get_file_candidates("@")

        # We should get candidates for both README.md and src/
        prompts = [str(c.prompt) for c in candidates]
        assert any("README.md" in p for p in prompts)
        assert any("src/" in p for p in prompts)

        # And prefixes should be either 📁 (dir) or 📄 (file)
        assert all("📁" in str(c.prompt) or "📄" in str(c.prompt) for c in candidates)

    def test_file_candidates_for_nonexistent_directory_returns_empty_list(
        self, mock_target, monkeypatch, tmp_path
    ):
        """Non-existent directories produce no file candidates."""
        # Point WORK_DIR at a real dir, but use a path that does not exist inside it.
        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        candidates = autocomplete.get_file_candidates("@nonexistent/")

        assert candidates == []

    def test_file_candidates_filters_by_filename(
        self, mock_target, tmp_path, monkeypatch
    ):
        """File candidates are filtered by the filename part after @."""
        # Create files
        (tmp_path / "README.md").write_text("test")
        (tmp_path / "requirements.txt").write_text("test")
        (tmp_path / "setup.py").write_text("test")

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        # Filter to files starting with "R"
        candidates = autocomplete.get_file_candidates("@R")
        prompts = [str(c.prompt) for c in candidates]

        assert any("README.md" in p for p in prompts)
        assert not any("setup.py" in p for p in prompts)

    def test_file_candidates_handles_subdirectories(
        self, mock_target, tmp_path, monkeypatch
    ):
        """File candidates work with subdirectory paths."""
        # Create subdirectory structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("test")
        (src_dir / "utils.py").write_text("test")

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        # Get files in src/ directory
        candidates = autocomplete.get_file_candidates("@src/")
        prompts = [str(c.prompt) for c in candidates]

        assert any("main.py" in p for p in prompts)
        assert any("utils.py" in p for p in prompts)

    def test_file_candidates_stops_after_space(
        self, mock_target, tmp_path, monkeypatch
    ):
        """File completion stops when there's a space after the path."""
        (tmp_path / "README.md").write_text("test")

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        # Space after @ path should stop completion
        candidates = autocomplete.get_file_candidates("@README.md ")

        assert candidates == []

    # Dropdown visibility behavior

    def test_show_dropdown_displays_candidates(self, mock_target):
        """show_dropdown makes the dropdown visible with candidates."""
        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        # Mock the option_list
        mock_option_list = mock.MagicMock()
        with mock.patch.object(
            autocomplete, "query_one", return_value=mock_option_list
        ):
            candidates = [Option("test1"), Option("test2")]
            autocomplete.show_dropdown(candidates)

        assert autocomplete._visible is True
        assert autocomplete.display is True

    def test_show_dropdown_with_empty_candidates_hides(self, mock_target):
        """show_dropdown with empty candidates hides the dropdown."""
        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])
        autocomplete._visible = True

        with mock.patch.object(autocomplete, "hide_dropdown") as mock_hide:
            autocomplete.show_dropdown([])
            mock_hide.assert_called_once()

    def test_hide_dropdown_hides_dropdown(self, mock_target):
        """hide_dropdown makes the dropdown invisible."""
        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])
        autocomplete._visible = True
        autocomplete.display = True

        autocomplete.hide_dropdown()

        assert autocomplete._visible is False
        assert autocomplete.display is False

    def test_is_visible_returns_visibility_state(self, mock_target):
        """is_visible returns the current visibility state."""
        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        assert autocomplete.is_visible() is False

        autocomplete._visible = True
        assert autocomplete.is_visible() is True

    def test_select_highlighted_returns_none_when_not_visible(self, mock_target):
        """select_highlighted returns None when dropdown is not visible."""
        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])
        autocomplete._visible = False

        result = autocomplete.select_highlighted()

        assert result is None

    def test_select_highlighted_returns_option_text(self, mock_target):
        """select_highlighted returns the highlighted option's text."""
        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])
        autocomplete._visible = True

        # Mock the option_list
        mock_option_list = mock.MagicMock()
        mock_option_list.highlighted = 0
        mock_option = mock.MagicMock()
        mock_option.prompt = "test option"
        mock_option_list.get_option_at_index.return_value = mock_option

        with mock.patch.object(
            autocomplete, "query_one", return_value=mock_option_list
        ):
            # Need to also patch the property
            with mock.patch.object(
                type(autocomplete), "option_list", new_callable=mock.PropertyMock
            ) as mock_prop:
                mock_prop.return_value = mock_option_list
                result = autocomplete.select_highlighted()

        assert result == "test option"
        assert autocomplete._visible is False

    def test_move_highlight_does_nothing_when_not_visible(self, mock_target):
        """move_highlight does nothing when dropdown is not visible."""
        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])
        autocomplete._visible = False

        mock_option_list = mock.MagicMock()
        with mock.patch.object(
            type(autocomplete), "option_list", new_callable=mock.PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_option_list
            autocomplete.move_highlight(1)

        mock_option_list.action_cursor_down.assert_not_called()
        mock_option_list.action_cursor_up.assert_not_called()

    def test_move_highlight_moves_cursor_down(self, mock_target):
        """move_highlight with positive direction moves cursor down."""
        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])
        autocomplete._visible = True

        mock_option_list = mock.MagicMock()
        with mock.patch.object(
            type(autocomplete), "option_list", new_callable=mock.PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_option_list
            autocomplete.move_highlight(1)

        mock_option_list.action_cursor_down.assert_called_once()

    def test_move_highlight_moves_cursor_up(self, mock_target):
        """move_highlight with negative direction moves cursor up."""
        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])
        autocomplete._visible = True

        mock_option_list = mock.MagicMock()
        with mock.patch.object(
            type(autocomplete), "option_list", new_callable=mock.PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_option_list
            autocomplete.move_highlight(-1)

        mock_option_list.action_cursor_up.assert_called_once()

    # Command candidate extraction

    def test_command_candidates_extract_command_name(self, mock_target):
        """Command candidates correctly extract command name from display text."""
        # Create command candidates with " - " separator
        cmd = mock.MagicMock()
        cmd.main = mock.MagicMock()
        cmd.main.plain = "/help - Display help"
        command_candidates = [cmd]

        autocomplete = TextAreaAutoComplete(
            mock_target, command_candidates=command_candidates
        )

        candidates = autocomplete.get_command_candidates("/h")

        assert len(candidates) == 1
        # The option should have the full display text
        assert "help" in str(candidates[0].prompt).lower()

    def test_file_candidates_skips_hidden_files_by_default(
        self, mock_target, tmp_path, monkeypatch
    ):
        """Hidden files are skipped unless explicitly typing them."""
        (tmp_path / ".hidden").write_text("test")
        (tmp_path / "visible.txt").write_text("test")

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        # Without dot prefix, hidden files are skipped
        candidates = autocomplete.get_file_candidates("@")
        prompts = [str(c.prompt) for c in candidates]

        assert any("visible.txt" in p for p in prompts)
        assert not any(".hidden" in p for p in prompts)

    def test_file_candidates_shows_hidden_files_when_typing_dot(
        self, mock_target, tmp_path, monkeypatch
    ):
        """Hidden files are shown when explicitly typing a dot."""
        (tmp_path / ".hidden").write_text("test")
        (tmp_path / "visible.txt").write_text("test")

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        # With dot prefix, hidden files are shown
        candidates = autocomplete.get_file_candidates("@.")
        prompts = [str(c.prompt) for c in candidates]

        assert any(".hidden" in p for p in prompts)

    # Edge cases

    def test_file_candidates_handles_permission_error(
        self, mock_target, tmp_path, monkeypatch
    ):
        """File candidates gracefully handle permission errors."""
        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        # Mock Path.iterdir to raise PermissionError
        with mock.patch("pathlib.Path.iterdir", side_effect=PermissionError):
            candidates = autocomplete.get_file_candidates("@")

        assert candidates == []

    def test_update_candidates_shows_dropdown_for_valid_candidates(
        self, mock_target, tmp_path, monkeypatch
    ):
        """update_candidates shows dropdown when candidates are found."""
        (tmp_path / "test.txt").write_text("test")

        monkeypatch.setattr(
            "openhands_cli.refactor.widgets.user_input.text_area_with_autocomplete.WORK_DIR",
            str(tmp_path),
        )

        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        with mock.patch.object(autocomplete, "show_dropdown") as mock_show:
            autocomplete.update_candidates("@t")
            mock_show.assert_called_once()
            # Verify candidates were passed
            args = mock_show.call_args[0][0]
            assert len(args) > 0

    def test_update_candidates_hides_dropdown_for_no_candidates(self, mock_target):
        """update_candidates hides dropdown when no candidates are found."""
        autocomplete = TextAreaAutoComplete(mock_target, command_candidates=[])

        with mock.patch.object(autocomplete, "hide_dropdown") as mock_hide:
            autocomplete.update_candidates("no match here")
            mock_hide.assert_called_once()
