"""Web server functionality for serving OpenHands CLI as a web application."""

from textual_serve.server import Server


def launch_web_server(
    host: str = "0.0.0.0", port: int = 12000, debug: bool = False
) -> None:
    """Launch the OpenHands CLI as a web application.

    Args:
        host: Host to bind the web server to
        port: Port to bind the web server to
        debug: Enable debug mode for the web server
    """
    server = Server("uv run openhands", host=host, port=port)
    server.serve(debug=debug)
