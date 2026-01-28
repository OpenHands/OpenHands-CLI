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
    from tui_e2e.trajectory import load_trajectory
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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pytest_httpserver import HTTPServer
from werkzeug import Request, Response


if TYPE_CHECKING:
    from .trajectory import Trajectory, TrajectoryEvent


# Default mock token usage for all responses
DEFAULT_USAGE = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


@dataclass
class TrajectoryReplayState:
    """Tracks the state of trajectory replay across requests."""

    responses: list[TrajectoryEvent] = field(default_factory=list)
    current_index: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

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


class OpenAIResponseBuilder:
    """Builds OpenAI-compatible response formats from trajectory events."""

    @staticmethod
    def build_completion(
        completion_id: str,
        message: dict[str, Any],
        finish_reason: str = "stop",
    ) -> dict[str, Any]:
        """Build a chat completion response."""
        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "mock-llm",
            "choices": [
                {"index": 0, "message": message, "finish_reason": finish_reason}
            ],
            "usage": DEFAULT_USAGE,
        }

    @staticmethod
    def build_stream_chunk(
        completion_id: str,
        delta: dict[str, Any],
        finish_reason: str | None = None,
    ) -> dict[str, Any]:
        """Build a single streaming chunk."""
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "mock-llm",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }

    @classmethod
    def build_message_chunks(
        cls, completion_id: str, content: str, finish_reason: str = "stop"
    ) -> list[dict[str, Any]]:
        """Build streaming chunks for a text message response."""
        return [
            cls.build_stream_chunk(completion_id, {"role": "assistant", "content": ""}),
            cls.build_stream_chunk(completion_id, {"content": content}),
            cls.build_stream_chunk(completion_id, {}, finish_reason),
        ]

    @classmethod
    def build_tool_call_chunks(
        cls, completion_id: str, tool_call_id: str, tool_name: str, arguments: str
    ) -> list[dict[str, Any]]:
        """Build streaming chunks for a tool call response."""
        return [
            cls.build_stream_chunk(
                completion_id,
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": tool_call_id,
                            "type": "function",
                            "function": {"name": tool_name, "arguments": ""},
                        }
                    ],
                },
            ),
            cls.build_stream_chunk(
                completion_id,
                {"tool_calls": [{"index": 0, "function": {"arguments": arguments}}]},
            ),
            cls.build_stream_chunk(completion_id, {}, "tool_calls"),
        ]


class TrajectoryResponseConverter:
    """Converts trajectory events to OpenAI response format."""

    def convert_event(self, event: TrajectoryEvent) -> dict[str, Any]:
        """Convert a trajectory event to OpenAI response format."""
        if event.kind == "ActionEvent" and event.tool_call:
            return self._create_tool_call_response(event)
        elif event.kind == "MessageEvent" and event.llm_message:
            return self._create_message_response(event)
        return self.create_default_response()

    def create_default_response(
        self, content: str = "Task completed."
    ) -> dict[str, Any]:
        """Create a default response when no event is available or event is unhandled.

        This is intentionally public as it's used by external handlers when
        the trajectory replay state has no more events to replay.
        """
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        return {
            "completion": OpenAIResponseBuilder.build_completion(
                completion_id, {"role": "assistant", "content": content}
            ),
            "stream_chunks": OpenAIResponseBuilder.build_message_chunks(
                completion_id, content
            ),
        }

    def _create_tool_call_response(self, event: TrajectoryEvent) -> dict[str, Any]:
        """Create a tool call response from an ActionEvent."""
        tool_call = event.tool_call
        if not tool_call:
            return self.create_default_response()

        tool_call_id = tool_call.get("id", f"call_{uuid.uuid4().hex[:24]}")
        tool_name = tool_call.get("name", event.tool_name or "unknown")
        arguments = tool_call.get("arguments", "{}")
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

        message: dict[str, Any] = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {"name": tool_name, "arguments": arguments},
                }
            ],
        }

        return {
            "completion": OpenAIResponseBuilder.build_completion(
                completion_id, message, "tool_calls"
            ),
            "stream_chunks": OpenAIResponseBuilder.build_tool_call_chunks(
                completion_id, tool_call_id, tool_name, arguments
            ),
        }

    def _create_message_response(self, event: TrajectoryEvent) -> dict[str, Any]:
        """Create a message response from a MessageEvent."""
        llm_message = event.llm_message
        if not llm_message:
            return self.create_default_response()

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        content = self._extract_content(llm_message)

        return {
            "completion": OpenAIResponseBuilder.build_completion(
                completion_id, {"role": "assistant", "content": content}
            ),
            "stream_chunks": OpenAIResponseBuilder.build_message_chunks(
                completion_id, content
            ),
        }

    @staticmethod
    def _extract_content(llm_message: dict[str, Any]) -> str:
        """Extract text content from an LLM message."""
        content = llm_message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            )
        return ""


def _format_sse_response(chunks: list[dict[str, Any]]) -> str:
    """Format chunks as Server-Sent Events response."""
    lines = [f"data: {json.dumps(chunk)}\n\n" for chunk in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines)


def create_request_handler(
    replay_state: TrajectoryReplayState,
    converter: TrajectoryResponseConverter,
):
    """Create a request handler function for pytest-httpserver."""

    def handler(request: Request) -> Response:
        """Handle all incoming requests."""
        path = request.path

        # Health check
        if path in ("/health", "/") and request.method == "GET":
            remaining = len(replay_state.responses) - replay_state.current_index
            return Response(
                json.dumps(
                    {
                        "status": "ok",
                        "server": "mock-llm-trajectory",
                        "responses_remaining": remaining,
                    }
                ),
                content_type="application/json",
            )

        # Reset endpoint
        if path == "/reset" and request.method == "GET":
            replay_state.reset()
            return Response(
                json.dumps({"status": "reset"}),
                content_type="application/json",
            )

        # Chat completions
        chat_paths = ("/chat/completions", "/v1/chat/completions")
        if path in chat_paths and request.method == "POST":
            try:
                request_data = json.loads(request.data)
            except json.JSONDecodeError:
                return Response(
                    json.dumps({"error": "Invalid JSON"}),
                    status=400,
                    content_type="application/json",
                )

            stream = request_data.get("stream", False)
            event = replay_state.get_next_response()
            if event is None:
                response = converter.create_default_response()
            else:
                response = converter.convert_event(event)

            if stream:
                return Response(
                    _format_sse_response(response["stream_chunks"]),
                    content_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            return Response(
                json.dumps(response["completion"]),
                content_type="application/json",
            )

        # Not found
        return Response(
            json.dumps({"error": "Not found"}),
            status=404,
            content_type="application/json",
        )

    return handler


class MockLLMServer:
    """Mock LLM server for e2e testing with trajectory replay.

    Uses pytest-httpserver for simplified HTTP handling while preserving
    the trajectory replay logic for deterministic testing.
    """

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
        self._server: HTTPServer | None = None
        self._replay_state: TrajectoryReplayState | None = None
        self._converter = TrajectoryResponseConverter()

    def start(self) -> str:
        """Start the mock server.

        Returns:
            The base URL of the server (e.g., http://127.0.0.1:8123)
        """
        # Create replay state from trajectory
        responses = self.trajectory.get_llm_responses() if self.trajectory else []
        self._replay_state = TrajectoryReplayState(responses=responses)

        # Create and configure server
        self._server = HTTPServer(host=self.host, port=self.port)
        handler = create_request_handler(self._replay_state, self._converter)
        self._server.expect_request("").respond_with_handler(handler)
        self._server.start()

        self.port = self._server.port
        return f"http://{self.host}:{self.port}"

    def stop(self) -> None:
        """Stop the mock server."""
        if self._server:
            self._server.clear()
            if self._server.is_running():
                self._server.stop()
            self._server = None

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
