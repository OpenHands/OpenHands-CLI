"""Cloud conversation runner for the Textual TUI.

Uses the runtime Socket.IO websocket feed (no polling fallback).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Callable
from typing import Any

import websockets

from openhands_cli.cloud.runtime_client import CloudRuntimeClient


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
        poll_interval_s: float = 1.0,
    ) -> None:
        self._runtime_host = runtime_host
        self._session_api_key = session_api_key
        self._conversation_id = conversation_id
        self._on_event = on_event
        self._on_error = on_error
        self._poll_interval_s = poll_interval_s

        self._client = CloudRuntimeClient(
            runtime_host=runtime_host, session_api_key=session_api_key
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_event_id: int | None = None

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
                limit=200,
            )
            for ev in events:
                self._on_event(ev)
                ev_id = ev.get("id")
                if isinstance(ev_id, int):
                    seen_max = ev_id if seen_max is None else max(seen_max, ev_id)
            if not has_more:
                break
            # If server paginates, continue from the next id.
            start_id = (seen_max + 1) if seen_max is not None else start_id + 200
        self._last_event_id = seen_max

    def start_streaming(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()

    def stop_streaming(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._thread = None

    def _stream_loop(self) -> None:
        try:
            asyncio.run(self._stream_loop_async())
        except RuntimeError:
            # Fallback in environments with an already running loop.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._stream_loop_async())
            loop.close()

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

            last_activity = time.time()

            while not self._stop.is_set():
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                except TimeoutError:
                    # Keep the connection alive; websocket lib also sends ping frames,
                    # but Socket.IO uses Engine.IO text pings (`2`).
                    continue

                if not isinstance(msg, str) or not msg:
                    continue

                last_activity = time.time()

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
                _ = last_activity

    def send_user_message(self, message: str) -> None:
        self._client.send_user_message(
            conversation_id=self._conversation_id, message=message
        )
