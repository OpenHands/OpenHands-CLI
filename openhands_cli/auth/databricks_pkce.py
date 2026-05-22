"""Databricks U2M PKCE browser flow for the CLI.

Runs an inline OAuth 2.0 Authorization Code + PKCE flow entirely within the CLI:
  1. Generate PKCE verifier / challenge and random state.
  2. Start a local HTTP server on ``localhost:<callback_port>/callback``.
  3. Open the system browser to the Databricks OIDC authorize URL.
  4. Wait (up to ``timeout_s``) for the browser to redirect back with ``?code=``.
  5. Exchange the code for tokens and return them.

The returned dict has keys: ``access_token``, ``refresh_token``, ``expires_at``,
``client_id``, ``host``.  The caller is responsible for storing/using the tokens.

The default callback port is 8080; the redirect URI registered in the Databricks
account console *must* match: ``http://localhost:<callback_port>/callback``.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import time
import webbrowser
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx


# ---------------------------------------------------------------------------
# PKCE primitives (mirrors openhands.app_server.auth.databricks_oauth)
# ---------------------------------------------------------------------------


def _generate_pkce() -> tuple[str, str]:
    """Return (verifier, challenge). Challenge is S256 of verifier."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _build_authorize_url(
    host: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    challenge: str,
) -> str:
    host = host.rstrip("/")
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "all-apis offline_access",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{host}/oidc/v1/authorize?{urlencode(params)}"


def _exchange_code_for_tokens(
    host: str,
    client_id: str,
    redirect_uri: str,
    code: str,
    verifier: str,
    client_secret: str | None = None,
) -> dict[str, Any]:
    try:
        from openhands.sdk.llm.providers.databricks.utils import USER_AGENT
    except ImportError:
        USER_AGENT = "OpenHandsOSS/unknown"

    host = host.rstrip("/")
    token_data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    if client_secret:
        token_data["client_secret"] = client_secret

    resp = httpx.post(
        f"{host}/oidc/v1/token",
        data=token_data,
        headers={"User-Agent": USER_AGENT},
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_at": time.time() + data.get("expires_in", 3600),
        "client_id": client_id,
        "host": host,
    }


# ---------------------------------------------------------------------------
# Async browser PKCE flow
# ---------------------------------------------------------------------------

_HTML_SUCCESS = """\
<!DOCTYPE html>
<html>
<head><title>OpenHands — Signed in</title>
<style>body{font-family:sans-serif;padding:40px;text-align:center}
h2{color:#2d7d46}</style></head>
<body><h2>&#10003; Signed in successfully</h2>
<p>You can close this tab and return to the terminal.</p></body>
</html>
"""

_HTML_ERROR = """\
<!DOCTYPE html>
<html>
<head><title>OpenHands — Auth error</title>
<style>body{font-family:sans-serif;padding:40px;text-align:center}
h2{color:#c0392b}</style></head>
<body><h2>&#10007; Authentication error</h2>
<p>{message}</p><p>Return to the terminal for details.</p></body>
</html>
"""


async def run_browser_pkce_flow(
    host: str,
    client_id: str,
    *,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
    callback_port: int = 8080,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """Run the full browser-based PKCE flow and return a tokens dict.

    Opens the system browser to the Databricks OIDC authorize URL, starts a
    local HTTP server to receive the callback, then exchanges the code for
    tokens.

    Args:
        host: Databricks workspace URL (e.g. ``https://adb-xxx.cloud.databricks.com``).
        client_id: OAuth App client ID from Databricks account console.
        client_secret: Required only for confidential (non-public) OAuth apps.
        redirect_uri: Full callback URL registered in the Databricks OAuth app.
            Defaults to ``http://localhost:<callback_port>/callback``.
            When provided, ``callback_port`` is derived from the URI's port.
        callback_port: Local port to listen on. Overridden by the port in
            ``redirect_uri`` when that argument is supplied.
        timeout_s: Seconds to wait for the browser callback before timing out.

    Returns:
        Dict with ``access_token``, ``refresh_token``, ``expires_at``,
        ``client_id``, ``host``.

    Raises:
        TimeoutError: If the browser callback does not arrive within ``timeout_s``.
        RuntimeError: If the OAuth server returns an error parameter.
        httpx.HTTPStatusError: If the token exchange fails.
    """
    if redirect_uri:
        # Extract port from the caller-supplied URI so the local server
        # listens on the right port.
        try:
            parsed_port = urlparse(redirect_uri).port
            if parsed_port:
                callback_port = parsed_port
        except Exception:
            pass
    else:
        redirect_uri = f"http://localhost:{callback_port}/callback"

    verifier, challenge = _generate_pkce()
    state = secrets.token_urlsafe(16)
    authorize_url = _build_authorize_url(host, client_id, redirect_uri, state, challenge)

    # Event set when callback arrives; result stored here.
    code_event: asyncio.Event = asyncio.Event()
    callback_result: dict[str, str] = {}

    async def _handle_request(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            request_line = data.decode(errors="replace").splitlines()[0]
            path = request_line.split(" ")[1] if " " in request_line else "/"
            parsed = urlparse(path)
            qs = parse_qs(parsed.query)
            code_list = qs.get("code", [])
            state_list = qs.get("state", [])
            error_list = qs.get("error", [])

            if error_list:
                callback_result["error"] = error_list[0]
                body = _HTML_ERROR.format(message=error_list[0]).encode()
            elif code_list and state_list and state_list[0] == state:
                callback_result["code"] = code_list[0]
                body = _HTML_SUCCESS.encode()
            else:
                callback_result["error"] = "invalid_state_or_missing_code"
                body = _HTML_ERROR.format(
                    message="Invalid state or missing code"
                ).encode()

            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html; charset=utf-8\r\n"
                b"Connection: close\r\n"
                + f"Content-Length: {len(body)}\r\n".encode()
                + b"\r\n"
                + body
            )
            writer.write(response)
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            code_event.set()

    server = await asyncio.start_server(_handle_request, "127.0.0.1", callback_port)
    try:
        webbrowser.open(authorize_url)
        await asyncio.wait_for(code_event.wait(), timeout=timeout_s)
    except asyncio.TimeoutError:
        raise TimeoutError(
            f"Browser authentication timed out after {timeout_s:.0f} seconds. "
            "Please complete sign-in in the browser window and try again."
        )
    finally:
        server.close()
        await server.wait_closed()

    if "error" in callback_result:
        raise RuntimeError(
            f"Databricks OAuth error: {callback_result['error']}"
        )

    code = callback_result["code"]
    return _exchange_code_for_tokens(
        host, client_id, redirect_uri, code, verifier, client_secret
    )
