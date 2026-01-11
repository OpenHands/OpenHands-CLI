"""Cloud conversation runner for the Textual TUI.

Uses the runtime Socket.IO websocket feed (no polling fallback).
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from typing import Any

import websockets

from openhands.sdk import get_logger
from openhands_cli.cloud.runtime_client import CloudRuntimeClient


logger = get_logger(__name__)


class CloudConversationRunner:
    """Minimal runner for a cloud conversation (runtime host)."""

    def __init__(
        self,
        *,
        runtime_host: str,
        session_api_key: str,
        conversation_id: str,
        on_event: Callable[[dict[str, Any]], None],
        on_error: Callable[[str], None],
    ) -> None:
        self._runtime_host = runtime_host
        self._session_api_key = session_api_key
        self._conversation_id = conversation_id
        self._on_event = on_event
        self._on_error = on_error

        self._client = CloudRuntimeClient(
            runtime_host=runtime_host, session_api_key=session_api_key
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_event_id: int | None = None
        # Stream internals (set inside the streaming thread)
        self._loop: asyncio.AbstractEventLoop | None = None
        # websockets typing differs by version; keep it loose for pyright.
        self._ws: Any | None = None
        self._stream_task: asyncio.Task[None] | None = None
        self._read_only: bool = False

    @property
    def conversation_id(self) -> str:
        return self._conversation_id

    def close(self) -> None:
        self.stop_streaming()
        self._client.close()

    def load_history(self) -> None:
        """Load the full event history (best-effort) and emit via callback."""
        start_id = 0
        seen_max: int | None = None
        while True:
            events, has_more = self._client.get_events(
                conversation_id=self._conversation_id,
                start_id=start_id,
                limit=CloudRuntimeClient.MAX_EVENTS_LIMIT,
            )
            for ev in events:
                self._on_event(ev)
                ev_id = ev.get("id")
                if isinstance(ev_id, int):
                    seen_max = ev_id if seen_max is None else max(seen_max, ev_id)
            if not has_more:
                break
            # If server paginates, continue from the next id.
            start_id = (
                (seen_max + 1)
                if seen_max is not None
                else start_id + CloudRuntimeClient.MAX_EVENTS_LIMIT
            )
        self._last_event_id = seen_max

    def start_streaming(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()

    def stop_streaming(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._stop.set()
        # Wake up any pending `ws.recv()` immediately by closing the websocket
        # from the loop thread, instead of waiting for timeouts.
        loop = self._loop
        ws = self._ws
        task = self._stream_task
        if loop is not None:
            if ws is not None:
                loop.call_soon_threadsafe(self._safe_close_ws, ws)
            if task is not None:
                loop.call_soon_threadsafe(task.cancel)

        # Wait a bit longer than the recv timeout, so we can reliably stop.
        thread.join(timeout=7.0)
        if thread.is_alive():
            # Best-effort: don't lie about stopping. Keep thread ref so caller
            # can retry stopping later.
            self._on_error("Cloud stream did not stop within timeout.")
            return
        self._thread = None

    @staticmethod
    def _safe_close_ws(ws: Any) -> None:
        """Close websocket in the owning event loop thread."""
        try:
            asyncio.create_task(ws.close(code=1000))
        except Exception:
            logger.debug("Failed to close cloud websocket", exc_info=True)

    @staticmethod
    def _safe_close_loop(loop: asyncio.AbstractEventLoop) -> None:
        """Best-effort close of an event loop (called from loop thread)."""
        try:
            if loop.is_running():
                loop.stop()
        except Exception:
            logger.debug("Failed to stop cloud event loop", exc_info=True)

        try:
            loop.close()
        except Exception:
            logger.debug("Failed to close cloud event loop", exc_info=True)

    def _stream_loop(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        try:
            asyncio.set_event_loop(loop)
            self._stream_task = loop.create_task(self._stream_loop_async())
            loop.run_until_complete(self._stream_task)
        except asyncio.CancelledError:
            logger.debug("Cloud stream task cancelled")
        except Exception as e:
            self._on_error(f"Cloud stream crashed: {type(e).__name__}: {e}")
        finally:
            # Close loop and clear references to avoid cross-thread use-after-close.
            self._safe_close_loop(loop)
            self._loop = None
            self._stream_task = None
            self._ws = None

    async def _stream_loop_async(self) -> None:
        ws_base = self._runtime_host.replace("https://", "wss://").replace(
            "http://", "ws://"
        )
        ws_url = (
            f"{ws_base}/socket.io/"
            f"?EIO=4&transport=websocket"
            f"&conversation_id={self._conversation_id}"
            f"&session_api_key={self._session_api_key}"
        )

        async with websockets.connect(ws_url, open_timeout=10) as ws:
            self._ws = ws
            # Engine.IO open packet: `0{...}`
            _ = await ws.recv()

            # Socket.IO connect packet to default namespace.
            await ws.send("40")

            # Best-effort: join + subscribe to ensure we receive events.
            await ws.send(
                "42" + json.dumps(["join", {"conversation_id": self._conversation_id}])
            )
            await ws.send(
                "42"
                + json.dumps(["subscribe", {"conversation_id": self._conversation_id}])
            )

            while not self._stop.is_set():
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                except TimeoutError:
                    # Keep the connection alive; websocket lib also sends ping frames,
                    # but Socket.IO uses Engine.IO text pings (`2`).
                    continue

                if not isinstance(msg, str) or not msg:
                    continue

                # Engine.IO ping/pong
                if msg == "2":
                    await ws.send("3")
                    continue

                # Socket.IO event packet
                if msg.startswith("42"):
                    payload_raw = msg[2:]
                    try:
                        arr = json.loads(payload_raw)
                    except Exception:
                        continue

                    if (
                        isinstance(arr, list)
                        and len(arr) == 2
                        and arr[0] == "oh_event"
                        and isinstance(arr[1], dict)
                    ):
                        ev = arr[1]
                        ev_id = ev.get("id")
                        if isinstance(ev_id, int):
                            self._last_event_id = ev_id
                        self._on_event(ev)
                    continue

                # Socket.IO connect ack `40{...}` or other packets -> ignore
                continue

    def send_user_message(self, message: str) -> None:
        if self._read_only:
            raise RuntimeError("Cloud conversation is read-only (runtime unavailable).")
        self._client.send_user_message(
            conversation_id=self._conversation_id, message=message
        )

    def mark_read_only(self) -> None:
        """Mark conversation as read-only (e.g., finished runtime)."""
        self._read_only = True
