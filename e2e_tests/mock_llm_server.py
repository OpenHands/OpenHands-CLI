"""Mock LLM Server for E2E Testing.

This module provides a mock OpenAI-compatible LLM server that returns
predetermined responses with tool calls. Unlike generic mock servers (like llm-mock),
this server is specifically designed for OpenHands e2e testing by supporting
proper tool call responses in the format expected by the SDK.

Key Features:
- OpenAI-compatible /chat/completions endpoint
- Returns deterministic tool call responses based on input patterns
- Supports streaming and non-streaming modes
- No external dependencies beyond standard library + httpx

Note: The llm-mock project (https://github.com/piyook/llm-mock) was evaluated but
found unsuitable because it only provides lorem ipsum/stored text responses without
support for the tool call format required by OpenHands agents.
"""

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer


class MockLLMHandler(BaseHTTPRequestHandler):
    """HTTP handler for mock LLM requests."""

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
        """Handle GET requests - health check."""
        if self.path == "/health" or self.path == "/":
            self._send_json_response({"status": "ok", "server": "mock-llm"})
        else:
            self._send_json_response({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        """Handle POST requests - chat completions."""
        if self.path in ("/chat/completions", "/v1/chat/completions"):
            self._handle_chat_completions()
        else:
            self._send_json_response({"error": "Not found"}, 404)

    def _handle_chat_completions(self) -> None:
        """Handle chat completion requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            request_data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json_response({"error": "Invalid JSON"}, 400)
            return

        messages = request_data.get("messages", [])
        stream = request_data.get("stream", False)

        # Get the last user message
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            user_message = item.get("text", "")
                            break
                else:
                    user_message = content
                break

        # Generate response based on configuration or default behavior
        response = self._generate_response(user_message, messages)

        if stream:
            self._send_streaming_response(response["stream_chunks"])
        else:
            self._send_json_response(response["completion"])

    def _generate_response(
        self, user_message: str, messages: list
    ) -> dict:
        """Generate a response based on the user message and conversation state.

        This method determines the appropriate response based on:
        1. Whether a tool call has already been executed (check for tool role messages)
        2. The content of the user message

        The flow is:
        - First request: Return tool call to execute "echo hello world"
        - After tool execution: Return a finish response indicating completion
        """
        user_message_lower = user_message.lower()

        # If there's already been a tool execution, finish the conversation
        for msg in reversed(messages):
            if msg.get("role") == "tool":
                return self._create_finish_response()

        # Check for echo command pattern (first request)
        if "echo" in user_message_lower:
            echo_content = self._extract_echo_content(user_message)
            return self._create_terminal_tool_call_response(f"echo {echo_content}")

        # Check for finish/done pattern
        if any(word in user_message_lower for word in ["finish", "done", "complete"]):
            return self._create_finish_response()

        # Default: return a tool call to echo the task completion
        return self._create_terminal_tool_call_response("echo 'Task completed'")

    def _extract_echo_content(self, message: str) -> str:
        """Extract content to echo from a user message."""
        message_lower = message.lower()
        if "hello world" in message_lower:
            return "hello world"
        if "echo " in message_lower:
            # Find the echo command in the message
            idx = message_lower.find("echo ")
            if idx != -1:
                content = message[idx + 5:].strip()
                # Clean up quotes if present
                if content.startswith('"') and content.endswith('"'):
                    content = content[1:-1]
                elif content.startswith("'") and content.endswith("'"):
                    content = content[1:-1]
                return content or "hello world"
        return "hello world"

    def _create_terminal_tool_call_response(self, command: str) -> dict:
        """Create a response with a terminal tool call."""
        tool_call_id = f"call_{uuid.uuid4().hex[:24]}"
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

        # Build the tool call arguments
        tool_args = {
            "command": command,
            "summary": f"Execute: {command}",
            "security_risk": "LOW",
        }

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
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": "terminal",
                                    "arguments": json.dumps(tool_args),
                                },
                            }
                        ],
                    },
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
                                        "name": "terminal",
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
                                    "function": {"arguments": json.dumps(tool_args)},
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
                "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            },
        ]

        return {"completion": completion_response, "stream_chunks": stream_chunks}

    def _create_finish_response(self) -> dict:
        """Create a response indicating the task is complete."""
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        content = (
            "The task has been completed successfully. "
            "The echo command was executed."
        )

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


class MockLLMServer:
    """Mock LLM server for e2e testing."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        """Initialize the mock server.

        Args:
            host: Host to bind to (default: 127.0.0.1)
            port: Port to bind to (default: 0 for auto-assign)
        """
        self.host = host
        self.port = port
        self.server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        """Start the mock server in a background thread.

        Returns:
            The base URL of the server (e.g., http://127.0.0.1:8123)
        """
        self.server = HTTPServer((self.host, self.port), MockLLMHandler)
        # Get the actual port assigned (useful when port=0)
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

    def __enter__(self) -> "MockLLMServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    @property
    def base_url(self) -> str:
        """Get the base URL of the server."""
        return f"http://{self.host}:{self.port}"


def run_mock_server(port: int = 8765) -> None:
    """Run the mock server standalone for testing."""
    server = MockLLMServer(port=port)
    base_url = server.start()
    print(f"Mock LLM server running at {base_url}")
    print("Endpoints:")
    print(f"  - GET  {base_url}/health")
    print(f"  - POST {base_url}/chat/completions")
    print("\nPress Ctrl+C to stop...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()


if __name__ == "__main__":
    run_mock_server()
