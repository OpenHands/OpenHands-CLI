"""Tests for web command functionality."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from openhands_cli.argparsers.main_parser import create_main_parser
from openhands_cli.simple_main import main


class TestWebParser:
    """Test the web argument parser."""

    def test_web_parser_default_values(self):
        """Test that web parser has correct default values."""
        parser = create_main_parser()
        args = parser.parse_args(["web"])
        
        assert args.command == "web"
        assert args.host == "0.0.0.0"
        assert args.port == 12000
        assert args.debug is False

    def test_web_parser_custom_host(self):
        """Test web parser with custom host."""
        parser = create_main_parser()
        args = parser.parse_args(["web", "--host", "127.0.0.1"])
        
        assert args.command == "web"
        assert args.host == "127.0.0.1"
        assert args.port == 12000
        assert args.debug is False

    def test_web_parser_custom_port(self):
        """Test web parser with custom port."""
        parser = create_main_parser()
        args = parser.parse_args(["web", "--port", "8080"])
        
        assert args.command == "web"
        assert args.host == "0.0.0.0"
        assert args.port == 8080
        assert args.debug is False

    def test_web_parser_debug_flag(self):
        """Test web parser with debug flag."""
        parser = create_main_parser()
        args = parser.parse_args(["web", "--debug"])
        
        assert args.command == "web"
        assert args.host == "0.0.0.0"
        assert args.port == 12000
        assert args.debug is True

    def test_web_parser_all_options(self):
        """Test web parser with all options."""
        parser = create_main_parser()
        args = parser.parse_args([
            "web", 
            "--host", "localhost", 
            "--port", "3000", 
            "--debug"
        ])
        
        assert args.command == "web"
        assert args.host == "localhost"
        assert args.port == 3000
        assert args.debug is True


class TestWebCommandIntegration:
    """Test web command integration with main entry point."""

    @patch("openhands_cli.serve.launch_web_server")
    def test_web_command_calls_launch_web_server(self, mock_launch_web_server):
        """Test that web command calls launch_web_server function."""
        with patch("sys.argv", ["openhands", "web"]):
            main()
        
        mock_launch_web_server.assert_called_once_with(
            host="0.0.0.0", 
            port=12000, 
            debug=False
        )

    @patch("openhands_cli.serve.launch_web_server")
    def test_web_command_with_custom_args(self, mock_launch_web_server):
        """Test web command with custom arguments."""
        with patch("sys.argv", [
            "openhands", "web", 
            "--host", "127.0.0.1", 
            "--port", "8080", 
            "--debug"
        ]):
            main()
        
        mock_launch_web_server.assert_called_once_with(
            host="127.0.0.1", 
            port=8080, 
            debug=True
        )

    def test_web_command_help(self, capsys):
        """Test that web command help displays correctly."""
        with patch("sys.argv", ["openhands", "web", "--help"]):
            with pytest.raises(SystemExit) as exc:
                main()
            
            assert exc.value.code == 0
            
            captured = capsys.readouterr()
            assert "--host HOST" in captured.out
            assert "--port PORT" in captured.out
            assert "--debug" in captured.out
            assert "Host to bind the web server to" in captured.out
            assert "Port to bind the web server to" in captured.out
            assert "Enable debug mode for the web server" in captured.out


class TestLaunchWebServerFunction:
    """Test the launch_web_server function directly."""

    @patch("openhands_cli.serve.Server")
    def test_launch_web_server_default_args(self, mock_server_class):
        """Test launch_web_server with default arguments."""
        from openhands_cli.serve import launch_web_server
        
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server
        
        launch_web_server()
        
        # Verify Server was created with correct arguments
        mock_server_class.assert_called_once_with(
            "uv run openhands --exp", 
            host="0.0.0.0", 
            port=12000
        )
        
        # Verify serve was called with debug=False
        mock_server.serve.assert_called_once_with(debug=False)

    @patch("openhands_cli.serve.Server")
    def test_launch_web_server_custom_args(self, mock_server_class):
        """Test launch_web_server with custom arguments."""
        from openhands_cli.serve import launch_web_server
        
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server
        
        launch_web_server(host="localhost", port=3000, debug=True)
        
        # Verify Server was created with correct arguments
        mock_server_class.assert_called_once_with(
            "uv run openhands --exp", 
            host="localhost", 
            port=3000
        )
        
        # Verify serve was called with debug=True
        mock_server.serve.assert_called_once_with(debug=True)

    @patch("openhands_cli.serve.Server")
    def test_launch_web_server_server_exception(self, mock_server_class):
        """Test launch_web_server handles server exceptions."""
        from openhands_cli.serve import launch_web_server
        
        mock_server = MagicMock()
        mock_server.serve.side_effect = Exception("Server error")
        mock_server_class.return_value = mock_server
        
        # Should propagate the exception
        with pytest.raises(Exception, match="Server error"):
            launch_web_server()