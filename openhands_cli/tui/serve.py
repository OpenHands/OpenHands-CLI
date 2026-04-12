"""Web server functionality for serving OpenHands CLI as a web application."""

from typing import Any
from urllib.parse import urlparse, urlunparse

import aiohttp_jinja2
from aiohttp import web
from textual_serve.server import Server, to_int


_VALID_PROTOS = {"http", "https"}


class ProxyAwareServer(Server):
    """A Server subclass that generates URLs based on the incoming request.

    The base textual-serve Server hardcodes URLs using its ``public_url``
    (e.g. ``http://0.0.0.0:12000``).  When the server sits behind a
    reverse-proxy the browser receives those unreachable addresses and can
    load neither static assets nor the WebSocket.  This subclass overrides
    ``handle_index`` to derive every URL from the *request* headers so
    everything works transparently through proxies.

    NOTE: ``handle_index`` is a full override of ``Server.handle_index``
    (textual-serve 1.1.3) because URL generation uses local closures over
    ``self.public_url`` — there is no smaller hook to override.  If
    textual-serve is upgraded, verify this method stays in sync with the
    upstream implementation.
    """

    @staticmethod
    def _get_base_url(request: web.Request) -> str:
        """Derive the external base URL from request headers.

        Checks ``X-Forwarded-Proto`` / ``X-Forwarded-Host`` first (common
        reverse-proxy headers), then falls back to the ``Host`` header.
        Basic validation is applied: proto must be http or https, and host
        must be a reasonable non-empty string.
        """
        proto = request.headers.get("X-Forwarded-Proto", request.scheme)
        host = request.headers.get("X-Forwarded-Host", request.host)

        # Sanitise proto – fall back to request.scheme on unexpected values
        if proto not in _VALID_PROTOS:
            proto = request.scheme

        # Sanitise host – reject empty, multi-line, or excessively long values
        if not host or "\n" in host or "\r" in host or len(host) > 253:
            host = request.host

        return f"{proto}://{host}"

    @aiohttp_jinja2.template("app_index.html")
    async def handle_index(self, request: web.Request) -> dict[str, Any]:
        base_url = self._get_base_url(request)
        router = request.app.router
        font_size = to_int(request.query.get("fontsize", "16"), 16)

        def get_url(route: str, **kwargs: str) -> str:
            path = router[route].url_for(**kwargs)
            return f"{base_url}{path}"

        def get_websocket_url(route: str, **kwargs: str) -> str:
            url = get_url(route, **kwargs)
            parsed = urlparse(url)
            ws_scheme = "wss" if parsed.scheme == "https" else "ws"
            return urlunparse(parsed._replace(scheme=ws_scheme))

        return {
            "font_size": font_size,
            "app_websocket_url": get_websocket_url("websocket"),
            "config": {
                "static": {
                    "url": get_url("static", filename="/").rstrip("/") + "/",
                },
            },
            "application": {
                "name": self.title,
            },
        }


def launch_web_server(
    host: str = "0.0.0.0", port: int = 12000, debug: bool = False
) -> None:
    """Launch the OpenHands CLI as a web application.

    Args:
        host: Host to bind the web server to
        port: Port to bind the web server to
        debug: Enable debug mode for the web server
    """
    server = ProxyAwareServer("uv run openhands", host=host, port=port)
    server.serve(debug=debug)
