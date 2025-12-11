"""Minimal high-impact tests for MCP argument parser help functionality."""

import argparse
import io
from contextlib import redirect_stderr

import pytest

from openhands_cli.argparsers.mcp_parser import MCPArgumentParser, add_mcp_parser


class TestMCPParserErrorHandling:
    """High-impact tests focusing on error handling and help display."""

    def test_custom_error_method_shows_full_help(self):
        """Test that the custom error method shows full help instead of just usage."""
        parser = MCPArgumentParser(
            description="Test parser with examples",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument("--required", required=True, help="A required argument")
        parser.add_argument("positional", help="A positional argument")

        stderr_capture = io.StringIO()

        with redirect_stderr(stderr_capture):
            with pytest.raises(SystemExit) as exc_info:
                parser.parse_args(
                    ["--required", "value"]
                )  # Missing positional argument

        assert exc_info.value.code == 2
        output = stderr_capture.getvalue()
        assert "usage:" in output
        assert "Test parser with examples" in output
        assert "Error: the following arguments are required: positional" in output

    @pytest.mark.parametrize(
        "command,missing_args,expected_error",
        [
            (
                "add",
                [],
                "the following arguments are required: --transport, name, target",
            ),
            (
                "add",
                ["--transport", "http"],
                "the following arguments are required: name, target",
            ),
            ("get", [], "the following arguments are required: name"),
            ("remove", [], "the following arguments are required: name"),
        ],
    )
    def test_missing_arguments_show_full_help_with_examples(
        self, command, missing_args, expected_error
    ):
        """Test that missing required arguments show full help with examples."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)

        stderr_capture = io.StringIO()

        with redirect_stderr(stderr_capture):
            with pytest.raises(SystemExit) as exc_info:
                main_parser.parse_args(["mcp", command] + missing_args)

        assert exc_info.value.code == 2
        output = stderr_capture.getvalue()

        # Verify full help is shown with examples
        assert "usage:" in output
        assert "Examples:" in output
        assert f"Error: {expected_error}" in output

    @pytest.mark.parametrize(
        "command,invalid_args,expected_error_pattern",
        [
            (
                "add",
                ["--transport", "invalid", "name", "target"],
                "invalid choice: 'invalid'",
            ),
            (
                "add",
                ["--auth", "invalid", "--transport", "http", "name", "target"],
                "invalid choice: 'invalid'",
            ),
        ],
    )
    def test_invalid_arguments_show_full_help_with_examples(
        self, command, invalid_args, expected_error_pattern
    ):
        """Test that invalid argument values show full help with examples."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)

        stderr_capture = io.StringIO()

        with redirect_stderr(stderr_capture):
            with pytest.raises(SystemExit) as exc_info:
                main_parser.parse_args(["mcp", command] + invalid_args)

        assert exc_info.value.code == 2
        output = stderr_capture.getvalue()

        # Verify full help is shown with examples
        assert "usage:" in output
        assert "Examples:" in output
        assert expected_error_pattern in output

    def test_unrecognized_argument_shows_mcp_help(self):
        """Test that unrecognized arguments (like --url) show MCP help with examples."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)

        stderr_capture = io.StringIO()

        with redirect_stderr(stderr_capture):
            with pytest.raises(SystemExit) as exc_info:
                # This reproduces the original issue: --url instead of positional target
                main_parser.parse_args(["mcp", "add", "--url", "https://example.com"])

        assert exc_info.value.code == 2
        output = stderr_capture.getvalue()

        # Should show MCP-specific help with examples
        assert "Examples:" in output
        assert "Add a new MCP server configuration" in output
        assert "Error:" in output

    def test_mcp_add_examples_content(self):
        """Test that MCP add command shows comprehensive examples on error."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)

        stderr_capture = io.StringIO()

        with redirect_stderr(stderr_capture):
            with pytest.raises(SystemExit):
                main_parser.parse_args(["mcp", "add"])  # Missing all required args

        output = stderr_capture.getvalue()

        # Verify key examples are present
        expected_examples = [
            "Add an HTTP server with Bearer token authentication",
            "openhands mcp add my-api https://api.example.com/mcp",
            "--transport http",
            '--header "Authorization: Bearer your-token-here"',
            "--transport stdio",
            "--auth oauth",
        ]

        for example in expected_examples:
            assert example in output

    def test_parser_uses_custom_error_class(self):
        """Test that MCP subparsers use the custom MCPArgumentParser class."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        mcp_parser = add_mcp_parser(subparsers)

        # Get the subparsers from the MCP parser
        mcp_subparsers_action = None
        for action in mcp_parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                mcp_subparsers_action = action
                break

        assert mcp_subparsers_action is not None
        assert mcp_subparsers_action._parser_class == MCPArgumentParser

    def test_successful_parsing_still_works(self):
        """Test that valid arguments still parse successfully (no regression)."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)

        # This should not raise an exception
        args = main_parser.parse_args(
            ["mcp", "add", "--transport", "http", "server-name", "https://example.com"]
        )

        assert args.command == "mcp"
        assert args.mcp_command == "add"
        assert args.transport == "http"
