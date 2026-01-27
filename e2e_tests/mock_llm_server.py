"""Mock LLM Server for E2E Testing with Trajectory Replay.

This module provides a mock OpenAI-compatible LLM server that replays
predetermined responses from trajectory JSON files. Each trajectory
represents a complete agent conversation that can be deterministically
replayed for e2e testing.

Key Features:
- OpenAI-compatible /chat/completions endpoint
- Replays responses from trajectory files in sequence
- Supports streaming and non-streaming modes
- Converts trajectory events to OpenAI response format

Usage:
    # Load a trajectory and create server
    from e2e_tests.trajectory import load_trajectory
    trajectory = load_trajectory("tests/trajectories/simple_echo_hello_world")

    server = MockLLMServer(trajectory=trajectory)
    base_url = server.start()

    # Server will replay LLM responses from the trajectory
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from .trajectory import Trajectory, TrajectoryEvent


class TrajectoryReplayState:
    """Tracks the state of trajectory replay across requests."""

    def __init__(self, responses: list[TrajectoryEvent]):
        self.responses = responses
        self.current_index = 0
        self._lock = threading.Lock()

    def get_next_response(self) -> TrajectoryEvent | None:
        """Get the next response to replay, advancing the index."""
        with self._lock:
            if self.current_index >= len(self.responses):
                return None
            response = self.responses[self.current_index]
            self.current_index += 1
            return response

    def peek_next_response(self) -> TrajectoryEvent | None:
        """Peek at the next response without advancing."""
        with self._lock:
            if self.current_index >= len(self.responses):
                return None
            return self.responses[self.current_index]

    def reset(self) -> None:
        """Reset replay to the beginning."""
        with self._lock:
            self.current_index = 0


def create_handler_class(replay_state: TrajectoryReplayState) -> type:
    """Create a handler class with access to the replay state."""

    class MockLLMHandler(BaseHTTPRequestHandler):
        """HTTP handler for mock LLM requests with trajectory replay."""

        def log_message(self, format: str, *args) -> None:
            """Suppress default logging."""
            pass

        def _send_json_response(self, data: dict, status: int = 200) -> None:
            """Send a JSON response."""
            response_body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def _send_streaming_response(self, chunks: list[dict]) -> None:
            """Send a streaming SSE response."""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            for chunk in chunks:
                chunk_data = f"data: {json.dumps(chunk)}\n\n"
                self.wfile.write(chunk_data.encode("utf-8"))
                self.wfile.flush()

            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

        def do_GET(self) -> None:
            """Handle GET requests - health check and status."""
            if self.path == "/health" or self.path == "/":
                self._send_json_response(
                    {
                        "status": "ok",
                        "server": "mock-llm-trajectory",
                        "responses_remaining": (
                            len(replay_state.responses) - replay_state.current_index
                        ),
                    }
                )
            elif self.path == "/reset":
                replay_state.reset()
                self._send_json_response({"status": "reset"})
            else:
                self._send_json_response({"error": "Not found"}, 404)

        def do_POST(self) -> None:
            """Handle POST requests - chat completions."""
            if self.path in ("/chat/completions", "/v1/chat/completions"):
                self._handle_chat_completions()
            else:
                self._send_json_response({"error": "Not found"}, 404)

        def _handle_chat_completions(self) -> None:
            """Handle chat completion requests by replaying trajectory."""
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                self._send_json_response({"error": "Invalid JSON"}, 400)
                return

            stream = request_data.get("stream", False)

            # Get the next response from the trajectory
            event = replay_state.get_next_response()
            if event is None:
                # No more responses - return a default finish
                response = self._create_default_finish_response()
            else:
                response = self._convert_event_to_response(event)

            if stream:
                self._send_streaming_response(response["stream_chunks"])
            else:
                self._send_json_response(response["completion"])

        def _convert_event_to_response(self, event: TrajectoryEvent) -> dict:
            """Convert a trajectory event to OpenAI response format."""
            if event.kind == "ActionEvent" and event.tool_call:
                return self._create_tool_call_response(event)
            elif event.kind == "MessageEvent" and event.llm_message:
                return self._create_message_response(event)
            else:
                return self._create_default_finish_response()

        def _create_tool_call_response(self, event: TrajectoryEvent) -> dict:
            """Create a tool call response from an ActionEvent."""
            tool_call = event.tool_call
            if not tool_call:
                return self._create_default_finish_response()

            tool_call_id = tool_call.get("id", f"call_{uuid.uuid4().hex[:24]}")
            tool_name = tool_call.get("name", event.tool_name or "unknown")
            arguments = tool_call.get("arguments", "{}")

            completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

            # Build thinking content if present
            thinking_content: list[dict[str, Any]] = []
            if event.thinking_blocks:
                for block in event.thinking_blocks:
                    if block.get("type") == "thinking":
                        thinking_content.append(
                            {
                                "type": "thinking",
                                "thinking": block.get("thinking", ""),
                            }
                        )

            # Build the message content
            message: dict[str, Any] = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": arguments,
                        },
                    }
                ],
            }

            completion_response = {
                "id": completion_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "mock-llm",
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }

            # Create streaming chunks
            stream_chunks = [
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "mock-llm",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": tool_call_id,
                                        "type": "function",
                                        "function": {
                                            "name": tool_name,
                                            "arguments": "",
                                        },
                                    }
                                ],
                            },
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "mock-llm",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {"arguments": arguments},
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "mock-llm",
                    "choices": [
                        {"index": 0, "delta": {}, "finish_reason": "tool_calls"}
                    ],
                },
            ]

            return {"completion": completion_response, "stream_chunks": stream_chunks}

        def _create_message_response(self, event: TrajectoryEvent) -> dict:
            """Create a message response from a MessageEvent."""
            llm_message = event.llm_message
            if not llm_message:
                return self._create_default_finish_response()

            completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

            # Extract content from llm_message
            content = llm_message.get("content", "")
            if isinstance(content, list):
                # Extract text from content array
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                content = "".join(text_parts)

            completion_response = {
                "id": completion_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "mock-llm",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": content,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }

            stream_chunks = [
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "mock-llm",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": ""},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "mock-llm",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": content},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "mock-llm",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                },
            ]

            return {"completion": completion_response, "stream_chunks": stream_chunks}

        def _create_default_finish_response(self) -> dict:
            """Create a default finish response when no trajectory events remain."""
            completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
            content = "Task completed."

            completion_response = {
                "id": completion_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "mock-llm",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": content,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }

            stream_chunks = [
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "mock-llm",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": ""},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "mock-llm",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": content},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "mock-llm",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                },
            ]

            return {"completion": completion_response, "stream_chunks": stream_chunks}

    return MockLLMHandler


class MockLLMServer:
    """Mock LLM server for e2e testing with trajectory replay."""

    def __init__(
        self,
        trajectory: Trajectory | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
    ):
        """Initialize the mock server.

        Args:
            trajectory: Trajectory to replay (optional). If not provided,
                       server returns default responses.
            host: Host to bind to (default: 127.0.0.1)
            port: Port to bind to (default: 0 for auto-assign)
        """
        self.host = host
        self.port = port
        self.trajectory = trajectory
        self.server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._replay_state: TrajectoryReplayState | None = None

    def start(self) -> str:
        """Start the mock server in a background thread.

        Returns:
            The base URL of the server (e.g., http://127.0.0.1:8123)
        """
        # Create replay state from trajectory
        if self.trajectory:
            responses = self.trajectory.get_llm_responses()
        else:
            responses = []
        self._replay_state = TrajectoryReplayState(responses)

        # Create handler class with replay state
        handler_class = create_handler_class(self._replay_state)

        self.server = HTTPServer((self.host, self.port), handler_class)
        actual_port = self.server.server_address[1]
        self.port = actual_port

        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

        base_url = f"http://{self.host}:{self.port}"
        return base_url

    def stop(self) -> None:
        """Stop the mock server."""
        if self.server:
            self.server.shutdown()
            self.server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def reset(self) -> None:
        """Reset trajectory replay to the beginning."""
        if self._replay_state:
            self._replay_state.reset()

    def __enter__(self) -> MockLLMServer:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    @property
    def base_url(self) -> str:
        """Get the base URL of the server."""
        return f"http://{self.host}:{self.port}"

    @property
    def replay_state(self) -> TrajectoryReplayState | None:
        """Get the replay state for inspection."""
        return self._replay_state


def run_mock_server(trajectory_path: str | None = None, port: int = 8765) -> None:
    """Run the mock server standalone for testing.

    Args:
        trajectory_path: Path to trajectory directory (optional)
        port: Port to run on
    """
    trajectory = None
    if trajectory_path:
        from .trajectory import load_trajectory

        trajectory = load_trajectory(trajectory_path)
        print(f"Loaded trajectory: {trajectory.name}")
        print(f"  - {len(trajectory.get_user_inputs())} user inputs")
        print(f"  - {len(trajectory.get_llm_responses())} LLM responses to replay")

    server = MockLLMServer(trajectory=trajectory, port=port)
    base_url = server.start()
    print(f"\nMock LLM server running at {base_url}")
    print("Endpoints:")
    print(f"  - GET  {base_url}/health")
    print(f"  - GET  {base_url}/reset")
    print(f"  - POST {base_url}/chat/completions")
    print("\nPress Ctrl+C to stop...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()


if __name__ == "__main__":
    import sys

    trajectory_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_mock_server(trajectory_path)
