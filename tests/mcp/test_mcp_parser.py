"""Unit tests for MCP argument parser help functionality."""

import argparse
import io
import sys
from contextlib import redirect_stderr
from unittest.mock import patch

import pytest

from openhands_cli.argparsers.mcp_parser import MCPArgumentParser, add_mcp_parser


class TestMCPArgumentParser:
    """Test cases for the custom MCPArgumentParser class."""

    def test_custom_error_method_shows_full_help(self):
        """Test that the custom error method shows full help instead of just usage."""
        parser = MCPArgumentParser(
            description="Test parser with examples",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument("--required", required=True, help="A required argument")
        parser.add_argument("positional", help="A positional argument")

        # Capture stderr to check the output
        stderr_capture = io.StringIO()
        
        with redirect_stderr(stderr_capture):
            with pytest.raises(SystemExit) as exc_info:
                parser.parse_args(["--required", "value"])  # Missing positional argument
        
        # Check that it exits with code 2 (argparse error)
        assert exc_info.value.code == 2
        
        # Check that the output contains both help and error message
        output = stderr_capture.getvalue()
        assert "usage:" in output
        assert "Test parser with examples" in output
        assert "positional arguments:" in output
        assert "options:" in output
        assert "Error: the following arguments are required: positional" in output

    def test_custom_error_method_with_invalid_choice(self):
        """Test custom error method with invalid choice error."""
        parser = MCPArgumentParser(description="Test parser")
        parser.add_argument("--transport", choices=["http", "stdio"], required=True)
        
        stderr_capture = io.StringIO()
        
        with redirect_stderr(stderr_capture):
            with pytest.raises(SystemExit) as exc_info:
                parser.parse_args(["--transport", "invalid"])
        
        assert exc_info.value.code == 2
        output = stderr_capture.getvalue()
        assert "usage:" in output
        assert "Error: argument --transport: invalid choice: 'invalid'" in output


class TestMCPParserIntegration:
    """Test cases for the complete MCP parser integration."""

    @pytest.fixture
    def mcp_parser(self):
        """Create a mock subparsers object and return the MCP parser."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        return add_mcp_parser(subparsers)

    def test_mcp_parser_creation(self, mcp_parser):
        """Test that MCP parser is created with correct structure."""
        assert mcp_parser is not None
        assert "mcp" in str(mcp_parser)

    @pytest.mark.parametrize("command,expected_in_help", [
        ("add", "Add a new MCP server configuration"),
        ("list", "List all configured MCP servers"),
        ("get", "Get details for a specific MCP server"),
        ("remove", "Remove an MCP server configuration"),
    ])
    def test_mcp_subcommand_help_content(self, command, expected_in_help):
        """Test that each MCP subcommand has proper help content."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        mcp_parser = add_mcp_parser(subparsers)
        
        # Capture help output (--help goes to stdout)
        from contextlib import redirect_stdout
        help_output = io.StringIO()
        with redirect_stdout(help_output):
            with pytest.raises(SystemExit):
                main_parser.parse_args(["mcp", command, "--help"])
        
        output = help_output.getvalue()
        assert expected_in_help in output
        assert "Examples:" in output

    @pytest.mark.parametrize("command,missing_args,expected_error", [
        ("add", [], "the following arguments are required: --transport, name, target"),
        ("add", ["--transport", "http"], "the following arguments are required: name, target"),
        ("add", ["--transport", "http", "server-name"], "the following arguments are required: target"),
        ("get", [], "the following arguments are required: name"),
        ("remove", [], "the following arguments are required: name"),
    ])
    def test_mcp_subcommand_missing_arguments_show_help(self, command, missing_args, expected_error):
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
        
        # Check that full help is shown
        assert "usage:" in output
        assert "Examples:" in output
        assert f"Error: {expected_error}" in output

    @pytest.mark.parametrize("command,invalid_args,expected_error_pattern", [
        ("add", ["--transport", "invalid", "name", "target"], "invalid choice: 'invalid'"),
        ("add", ["--auth", "invalid", "--transport", "http", "name", "target"], "invalid choice: 'invalid'"),
    ])
    def test_mcp_subcommand_invalid_arguments_show_help(self, command, invalid_args, expected_error_pattern):
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
        
        # Check that full help is shown
        assert "usage:" in output
        assert "Examples:" in output
        assert expected_error_pattern in output

    def test_mcp_list_command_no_required_args(self):
        """Test that list command works without required arguments."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)
        
        # This should not raise an exception
        args = main_parser.parse_args(["mcp", "list"])
        assert args.command == "mcp"
        assert args.mcp_command == "list"

    @pytest.mark.parametrize("command,valid_args", [
        ("add", ["--transport", "http", "server-name", "https://example.com"]),
        ("add", ["--transport", "stdio", "server-name", "python", "--", "-m", "server"]),
        ("add", ["--transport", "http", "server-name", "https://example.com", "--header", "Auth: Bearer token"]),
        ("add", ["--transport", "http", "server-name", "https://example.com", "--auth", "oauth"]),
        ("get", ["server-name"]),
        ("remove", ["server-name"]),
        ("list", []),
    ])
    def test_mcp_subcommand_valid_arguments_parse_successfully(self, command, valid_args):
        """Test that valid arguments parse successfully without showing help."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)
        
        # This should not raise an exception
        args = main_parser.parse_args(["mcp", command] + valid_args)
        assert args.command == "mcp"
        assert args.mcp_command == command

    def test_mcp_add_command_examples_in_help(self):
        """Test that MCP add command help contains comprehensive examples."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)
        
        from contextlib import redirect_stdout
        stdout_capture = io.StringIO()
        
        with redirect_stdout(stdout_capture):
            with pytest.raises(SystemExit):
                main_parser.parse_args(["mcp", "add", "--help"])
        
        output = stdout_capture.getvalue()
        
        # Check for specific examples
        expected_examples = [
            "Add an HTTP server with Bearer token authentication",
            "openhands mcp add my-api https://api.example.com/mcp",
            "--transport http",
            '--header "Authorization: Bearer your-token-here"',
            "Add a local stdio server with environment variables",
            "--transport stdio",
            '--env "API_KEY=secret123"',
            "Add an OAuth-based server",
            "--auth oauth",
        ]
        
        for example in expected_examples:
            assert example in output

    def test_mcp_parser_uses_custom_parser_class(self):
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

    @pytest.mark.parametrize("transport_type", ["http", "sse", "stdio"])
    def test_mcp_add_transport_choices(self, transport_type):
        """Test that all valid transport types are accepted."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)
        
        args = main_parser.parse_args([
            "mcp", "add", 
            "--transport", transport_type, 
            "server-name", 
            "target"
        ])
        
        assert args.mcp_command == "add"
        assert args.transport == transport_type

    def test_mcp_add_multiple_headers_and_env_vars(self):
        """Test that multiple headers and environment variables can be specified."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)
        
        args = main_parser.parse_args([
            "mcp", "add",
            "--transport", "http",
            "--header", "Authorization: Bearer token",
            "--header", "X-API-Key: key123",
            "--env", "VAR1=value1",
            "--env", "VAR2=value2",
            "server-name",
            "https://example.com"
        ])
        
        assert args.header == ["Authorization: Bearer token", "X-API-Key: key123"]
        assert args.env == ["VAR1=value1", "VAR2=value2"]

    def test_help_output_formatting(self):
        """Test that help output is properly formatted with RawDescriptionHelpFormatter."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)
        
        stderr_capture = io.StringIO()
        
        with redirect_stderr(stderr_capture):
            with pytest.raises(SystemExit):
                # Trigger error to see formatted help
                main_parser.parse_args(["mcp", "add"])
        
        output = stderr_capture.getvalue()
        
        # Check that formatting is preserved (backslashes should be visible)
        assert "\\" in output  # Line continuation characters should be preserved
        assert "Examples:" in output
        assert "# Add an HTTP server" in output  # Comments should be preserved


class TestMCPParserErrorScenarios:
    """Test various error scenarios and their help output."""

    def test_unrecognized_argument_shows_mcp_help(self):
        """Test that unrecognized arguments in MCP subcommand show MCP help."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)
        
        stderr_capture = io.StringIO()
        
        with redirect_stderr(stderr_capture):
            with pytest.raises(SystemExit) as exc_info:
                # This should be handled by MCP parser and show full help
                main_parser.parse_args(["mcp", "add", "--url", "https://example.com"])
        
        assert exc_info.value.code == 2
        output = stderr_capture.getvalue()
        
        # Should show MCP-specific help with examples
        assert "Examples:" in output
        assert "Add a new MCP server configuration" in output
        # Should contain error about unrecognized argument or missing required args
        assert "Error:" in output

    def test_mcp_command_without_subcommand(self):
        """Test MCP command without specifying a subcommand."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)
        
        stderr_capture = io.StringIO()
        
        with redirect_stderr(stderr_capture):
            with pytest.raises(SystemExit) as exc_info:
                main_parser.parse_args(["mcp"])
        
        assert exc_info.value.code == 2
        output = stderr_capture.getvalue()
        
        # Should show MCP parser help with available subcommands
        assert "usage:" in output
        assert "{add,list,get,remove}" in output or "add" in output

    @pytest.mark.parametrize("invalid_subcommand", ["invalid", "unknown", "test"])
    def test_invalid_mcp_subcommand(self, invalid_subcommand):
        """Test invalid MCP subcommands."""
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        add_mcp_parser(subparsers)
        
        stderr_capture = io.StringIO()
        
        with redirect_stderr(stderr_capture):
            with pytest.raises(SystemExit) as exc_info:
                main_parser.parse_args(["mcp", invalid_subcommand])
        
        assert exc_info.value.code == 2
        output = stderr_capture.getvalue()
        
        # Should show error about invalid choice
        assert f"invalid choice: '{invalid_subcommand}'" in output