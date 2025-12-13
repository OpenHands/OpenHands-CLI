"""Tests for ACP slash commands functionality."""

from unittest.mock import MagicMock

import pytest

from openhands_cli.acp_impl.confirmation import CONFIRMATION_MODES
from openhands_cli.acp_impl.slash_commands import (
    apply_confirmation_mode_to_conversation,
    create_help_text,
    get_available_slash_commands,
    get_confirm_error_text,
    get_confirm_help_text,
    get_confirm_success_text,
    get_unknown_command_text,
    handle_confirm_argument,
    parse_slash_command,
    validate_confirmation_mode,
)
from openhands_cli.utils import extract_text_from_message_content


class TestParseSlashCommand:
    """Test the slash command parser."""

    def test_parse_simple_command(self):
        """Test parsing a simple slash command without arguments."""
        result = parse_slash_command("/help")
        assert result == ("help", "")

    def test_parse_command_with_argument(self):
        """Test parsing a slash command with an argument."""
        result = parse_slash_command("/confirm always-ask")
        assert result == ("confirm", "always-ask")

    def test_parse_command_with_multiple_arguments(self):
        """Test parsing a slash command with multiple space-separated arguments."""
        result = parse_slash_command("/confirm toggle extra")
        assert result == ("confirm", "toggle extra")

    def test_parse_command_with_extra_spaces(self):
        """Test parsing handles extra spaces correctly."""
        result = parse_slash_command("/confirm   always-ask  ")
        assert result == ("confirm", "always-ask")

    def test_parse_non_command(self):
        """Test that non-slash-command text returns None."""
        result = parse_slash_command("regular message")
        assert result is None

    def test_parse_empty_string(self):
        """Test that empty string returns None."""
        result = parse_slash_command("")
        assert result is None

    def test_parse_slash_only(self):
        """Test that a lone slash returns None."""
        result = parse_slash_command("/")
        assert result is None

    def test_parse_slash_with_spaces(self):
        """Test that slash followed by spaces returns None."""
        result = parse_slash_command("/   ")
        assert result is None

    def test_parse_case_insensitive(self):
        """Test that command names are case-insensitive."""
        result = parse_slash_command("/HELP")
        assert result == ("help", "")

        result = parse_slash_command("/CoNfIrM always-ask")
        assert result == ("confirm", "always-ask")


class TestSlashCommandFunctions:
    """Test the slash command helper functions."""

    def test_get_available_commands(self):
        """Test getting available slash commands."""
        commands = get_available_slash_commands()
        assert len(commands) == 2

        # Check that both commands are present (without "/" prefix per ACP spec)
        command_names = {cmd.name for cmd in commands}
        assert command_names == {"help", "confirm"}

        # Check that descriptions exist
        help_cmd = next(cmd for cmd in commands if cmd.name == "help")
        assert help_cmd.description
        confirm_cmd = next(cmd for cmd in commands if cmd.name == "confirm")
        assert confirm_cmd.description

    def test_create_help_text(self):
        """Test creating help text."""
        help_text = create_help_text()
        assert help_text
        assert "Available slash commands" in help_text
        assert "/help" in help_text
        assert "/confirm" in help_text


class TestConfirmationModeValidation:
    """Test confirmation mode validation."""

    def test_validate_valid_modes(self):
        """Test validation of valid confirmation modes."""
        assert validate_confirmation_mode("always-ask") == "always-ask"
        assert validate_confirmation_mode("always-approve") == "always-approve"
        assert validate_confirmation_mode("llm-approve") == "llm-approve"

    def test_validate_case_insensitive(self):
        """Test that mode validation is case-insensitive."""
        assert validate_confirmation_mode("ALWAYS-ASK") == "always-ask"
        assert validate_confirmation_mode("Always-Approve") == "always-approve"
        assert validate_confirmation_mode("LLM-APPROVE") == "llm-approve"

    def test_validate_whitespace_handling(self):
        """Test that validation handles leading/trailing whitespace."""
        assert validate_confirmation_mode("  always-ask  ") == "always-ask"
        assert validate_confirmation_mode("\talways-approve\n") == "always-approve"

    def test_validate_invalid_mode(self):
        """Test validation of invalid modes."""
        assert validate_confirmation_mode("invalid") is None
        assert validate_confirmation_mode("on") is None
        assert validate_confirmation_mode("off") is None
        assert validate_confirmation_mode("") is None


class TestConfirmCommandHandling:
    """Test /confirm command handling logic."""

    def test_confirm_no_argument_shows_help(self):
        """Test /confirm with no argument shows help."""
        response, new_mode = handle_confirm_argument("always-ask", "")
        assert new_mode is None
        assert "Current confirmation mode: always-ask" in response
        assert "always-ask" in response
        assert "always-approve" in response
        assert "llm-approve" in response

    def test_confirm_whitespace_only_shows_help(self):
        """Test /confirm with whitespace shows help."""
        response, new_mode = handle_confirm_argument("always-ask", "   ")
        assert new_mode is None
        assert "Current confirmation mode" in response

    def test_confirm_valid_mode_returns_success(self):
        """Test /confirm with valid mode returns success message."""
        response, new_mode = handle_confirm_argument("always-ask", "always-approve")
        assert new_mode == "always-approve"
        assert "Confirmation mode set to: always-approve" in response
        assert CONFIRMATION_MODES["always-approve"]["long"] in response

    def test_confirm_all_valid_modes(self):
        """Test /confirm with all valid modes."""
        for mode in ["always-ask", "always-approve", "llm-approve"]:
            response, new_mode = handle_confirm_argument("always-ask", mode)
            assert new_mode == mode
            assert f"Confirmation mode set to: {mode}" in response

    def test_confirm_invalid_mode_shows_error(self):
        """Test /confirm with invalid mode shows error."""
        response, new_mode = handle_confirm_argument("always-ask", "invalid-mode")
        assert new_mode is None
        assert "Unknown mode: invalid-mode" in response
        assert "always-ask" in response
        assert "always-approve" in response
        assert "llm-approve" in response


class TestTextGeneration:
    """Test text generation functions."""

    def test_get_confirm_help_text(self):
        """Test confirm help text generation."""
        for mode in ["always-ask", "always-approve", "llm-approve"]:
            help_text = get_confirm_help_text(mode)  # type: ignore[arg-type]
            assert f"Current confirmation mode: {mode}" in help_text
            assert "Available modes:" in help_text
            assert "Usage: /confirm <mode>" in help_text

    def test_get_confirm_error_text(self):
        """Test confirm error text generation."""
        error_text = get_confirm_error_text("bad-mode", "always-ask")  # type: ignore[arg-type]
        assert "Unknown mode: bad-mode" in error_text
        assert "Current mode: always-ask" in error_text

    def test_get_confirm_success_text(self):
        """Test confirm success text generation."""
        for mode in ["always-ask", "always-approve", "llm-approve"]:
            success_text = get_confirm_success_text(mode)  # type: ignore[arg-type]
            assert f"Confirmation mode set to: {mode}" in success_text
            assert CONFIRMATION_MODES[mode]["long"] in success_text  # type: ignore[index]

    def test_get_unknown_command_text(self):
        """Test unknown command text generation."""
        error_text = get_unknown_command_text("badcmd")
        assert "Unknown command: /badcmd" in error_text
        assert "/help" in error_text
        assert "/confirm" in error_text


class TestExtractTextFromMessageContent:
    """Test text extraction from message content."""

    def test_extract_from_single_text_block(self):
        """Test extracting text from single text content block."""
        from openhands.sdk import TextContent

        content = [TextContent(text="Hello world")]
        result = extract_text_from_message_content(content)  # type: ignore[arg-type]
        assert result == "Hello world"

    def test_extract_returns_none_for_multiple_blocks(self):
        """Test that multiple blocks returns None (not a slash command)."""
        from openhands.sdk import TextContent

        content = [TextContent(text="Hello"), TextContent(text="world")]
        result = extract_text_from_message_content(content)  # type: ignore[arg-type]
        assert result is None

    def test_extract_returns_none_for_empty_list(self):
        """Test that empty content returns None."""
        result = extract_text_from_message_content([])
        assert result is None

    def test_extract_returns_none_for_image_content(self):
        """Test that image content returns None."""
        from openhands.sdk import ImageContent

        content = [ImageContent(image_urls=["https://example.com/image.png"])]
        result = extract_text_from_message_content(content)  # type: ignore[arg-type]
        assert result is None


class TestApplyConfirmationModeToConversation:
    """Test applying confirmation modes to conversations."""

    @pytest.fixture
    def mock_conversation(self):
        """Create a mock conversation."""
        conv = MagicMock()
        return conv

    def test_apply_always_ask_mode(self, mock_conversation):
        """Test applying always-ask mode sets AlwaysConfirm policy."""
        from openhands.sdk.security.confirmation_policy import AlwaysConfirm

        apply_confirmation_mode_to_conversation(
            mock_conversation, "always-ask", "test-session"
        )

        # Verify security analyzer was set
        mock_conversation.set_security_analyzer.assert_called_once()

        # Verify AlwaysConfirm policy was set
        mock_conversation.set_confirmation_policy.assert_called_once()
        policy = mock_conversation.set_confirmation_policy.call_args[0][0]
        assert isinstance(policy, AlwaysConfirm)

    def test_apply_always_approve_mode(self, mock_conversation):
        """Test applying always-approve mode sets NeverConfirm policy."""
        from openhands.sdk.security.confirmation_policy import NeverConfirm

        apply_confirmation_mode_to_conversation(
            mock_conversation, "always-approve", "test-session"
        )

        # Verify security analyzer was set
        mock_conversation.set_security_analyzer.assert_called_once()

        # Verify NeverConfirm policy was set
        mock_conversation.set_confirmation_policy.assert_called_once()
        policy = mock_conversation.set_confirmation_policy.call_args[0][0]
        assert isinstance(policy, NeverConfirm)

    def test_apply_llm_approve_mode(self, mock_conversation):
        """Test applying llm-approve mode sets ConfirmRisky policy."""
        from openhands.sdk.security.confirmation_policy import ConfirmRisky

        apply_confirmation_mode_to_conversation(
            mock_conversation, "llm-approve", "test-session"
        )

        # Verify security analyzer was set
        mock_conversation.set_security_analyzer.assert_called_once()

        # Verify ConfirmRisky policy was set
        mock_conversation.set_confirmation_policy.assert_called_once()
        policy = mock_conversation.set_confirmation_policy.call_args[0][0]
        assert isinstance(policy, ConfirmRisky)
