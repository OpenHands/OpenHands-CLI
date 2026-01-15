"""Minimal tests for web command functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openhands_cli.argparsers.main_parser import create_main_parser
from openhands_cli.entrypoint import main


@pytest.mark.parametrize(
    "argv, expected",
    [
        (["web"], dict(command="web", host="0.0.0.0", port=12000, debug=False)),
        (
            ["web", "--host", "127.0.0.1"],
            dict(command="web", host="127.0.0.1", port=12000, debug=False),
        ),
        (
            ["web", "--port", "8080"],
            dict(command="web", host="0.0.0.0", port=8080, debug=False),
        ),
        (
            ["web", "--debug"],
            dict(command="web", host="0.0.0.0", port=12000, debug=True),
        ),
        (
            ["web", "--host", "localhost", "--port", "3000", "--debug"],
            dict(command="web", host="localhost", port=3000, debug=True),
        ),
    ],
)
def test_web_parser_variants(argv, expected):
    parser = create_main_parser()
    args = parser.parse_args(argv)

    assert args.command == expected["command"]
    assert args.host == expected["host"]
    assert args.port == expected["port"]
    assert args.debug is expected["debug"]


@pytest.mark.parametrize(
    "sys_argv, expected_kwargs",
    [
        (["openhands", "web"], dict(host="0.0.0.0", port=12000, debug=False)),
        (
            ["openhands", "web", "--host", "127.0.0.1", "--port", "8080", "--debug"],
            dict(host="127.0.0.1", port=8080, debug=True),
        ),
    ],
)
@patch("openhands_cli.tui.serve.launch_web_server")
def test_web_command_calls_launch_web_server(
    mock_launch_web_server, sys_argv, expected_kwargs
):
    with patch("sys.argv", sys_argv):
        main()

    mock_launch_web_server.assert_called_once_with(**expected_kwargs)


def test_web_command_help_smoke(capsys):
    with patch("sys.argv", ["openhands", "web", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 0
    out = capsys.readouterr().out

    # High-impact smoke checks: options exist + one description string
    assert "--host" in out
    assert "--port" in out
    assert "--debug" in out
    assert "Host to bind the web server to" in out


@pytest.mark.parametrize(
    "kwargs, expected_host, expected_port, expected_debug",
    [
        ({}, "0.0.0.0", 12000, False),
        ({"host": "localhost", "port": 3000, "debug": True}, "localhost", 3000, True),
    ],
)
@patch("openhands_cli.tui.serve.Server")
def test_launch_web_server_constructs_and_serves(
    mock_server_class, kwargs, expected_host, expected_port, expected_debug
):
    from openhands_cli.tui.serve import launch_web_server

    mock_server = MagicMock()
    mock_server_class.return_value = mock_server

    launch_web_server(**kwargs)

    mock_server_class.assert_called_once_with(
        "uv run openhands",
        host=expected_host,
        port=expected_port,
    )
    mock_server.serve.assert_called_once_with(debug=expected_debug)


@patch("openhands_cli.tui.serve.Server")
def test_launch_web_server_propagates_exception(mock_server_class):
    from openhands_cli.tui.serve import launch_web_server

    mock_server = MagicMock()
    mock_server.serve.side_effect = Exception("Server error")
    mock_server_class.return_value = mock_server

    with pytest.raises(Exception, match="Server error"):
        launch_web_server()
