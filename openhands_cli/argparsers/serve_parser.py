"""Argument parser for serve subcommand."""

import argparse
import ipaddress
from urllib.parse import urlsplit


def validate_bind_address(value: str) -> str:
    """Validate that the bind address is a valid IP or IP:port combination.

    Supports:
    - IPv4 (e.g., 127.0.0.1)
    - IPv4:port (e.g., 127.0.0.1:3000)
    - IPv6 (e.g., ::1)
    - [IPv6]:port (e.g., [::1]:3000)

    Args:
        value: The string to validate

    Returns:
        The validated string

    Raises:
        argparse.ArgumentTypeError: If the value is invalid
    """
    if not value:
        raise argparse.ArgumentTypeError("Bind address cannot be empty")

    try:
        # urlsplit requires a scheme-like start to parse netloc correctly
        # We use // as a prefix to treat it as a network location
        parts = urlsplit(f"//{value}")
        host = parts.hostname
        port = parts.port

        if not host:
            raise ValueError("Could not parse host from bind address")

        # Validate IP
        ipaddress.ip_address(host)

        # Validate Port if present
        if port is not None:
            if not (1 <= port <= 65535):
                raise ValueError(f"Port {port} out of range")

        return value
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Invalid bind address: '{value}'. {str(e)}. "
            "Expected IP or IP:port (e.g., 127.0.0.1:3000 or [::1]:3000)"
        )


def add_serve_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add serve subcommand parser.

    Args:
        subparsers: The subparsers object to add the serve parser to

    Returns:
        The serve argument parser
    """
    serve_parser = subparsers.add_parser(
        "serve", help="Launch the OpenHands GUI server using Docker (web interface)"
    )
    serve_parser.add_argument(
        "--mount-cwd",
        help="Mount the current working directory into the GUI server container",
        action="store_true",
        default=False,
    )
    serve_parser.add_argument(
        "--gpu",
        help="Enable GPU support by mounting all GPUs into the Docker "
        "container via nvidia-docker",
        action="store_true",
        default=False,
    )
    serve_parser.add_argument(
        "--bind",
        help="Bind the GUI server to a specific IP or IP:port (e.g., 127.0.0.1 or 127.0.0.1:3000)",
        type=validate_bind_address,
        default="127.0.0.1:3000",
    )
    return serve_parser
