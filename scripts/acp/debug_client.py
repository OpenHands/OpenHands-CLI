#!/usr/bin/env python3
"""
Debug client for testing the OpenHands ACP server.

This tool allows you to interactively send JSON-RPC messages to the ACP server
and see the responses. Useful for debugging ACP protocol issues.

Usage:
    uv run python scripts/acp/debug_client.py

Commands:
    init              - Send initialize request
    new <cwd>         - Create a new session with the given working directory
    load <sessionId>  - Load an existing session
    prompt <message>  - Send a prompt to the current session
    raw <json>        - Send raw JSON-RPC message
    quit              - Exit the debug client
"""

import json
import os
import select
import subprocess
import sys
import threading
import time
from pathlib import Path


class ACPDebugClient:
    """Interactive debug client for ACP server."""

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.session_id: str | None = None
        self.message_id: int = 0
        self.reader_thread: threading.Thread | None = None
        self.running: bool = False

    def start_server(self):
        """Start the ACP server process."""
        print("Starting ACP server...")
        self.process = subprocess.Popen(
            ["uv", "run", "openhands", "acp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        print(f"✅ ACP server started (PID: {self.process.pid})")

        # Start background thread to read responses
        self.running = True
        self.reader_thread = threading.Thread(target=self._read_responses, daemon=True)
        self.reader_thread.start()

        # Give server time to start
        time.sleep(0.5)

    def _read_responses(self):
        """Background thread to read and print responses."""
        if not self.process or not self.process.stdout:
            return
        buffer = b""
        while self.running and self.process:
            try:
                # Check if there's data available
                ready, _, _ = select.select([self.process.stdout], [], [], 0.1)

                if ready and self.process.stdout:
                    chunk = self.process.stdout.read(1)
                    if not chunk:
                        break
                    buffer += chunk

                    # Try to parse complete JSON messages
                    if chunk == b"\n":
                        try:
                            response = json.loads(buffer.decode("utf-8"))
                            self._print_response(response)
                            buffer = b""
                        except json.JSONDecodeError:
                            # Not complete JSON yet, continue reading
                            pass

                # Check if process has terminated
                if self.process.poll() is not None:
                    exit_code = self.process.returncode
                    print(f"\n⚠️  Process terminated with exit code {exit_code}")
                    break

            except Exception as e:
                print(f"\n❌ Error reading response: {e}")
                break

    def _print_response(self, response):
        """Pretty print a JSON-RPC response."""
        print("\n📥 Response:")

        # Extract key info for better readability
        if "result" in response:
            print(f"   ✅ Success (ID: {response.get('id', 'N/A')})")
            result = response["result"]

            # Special handling for common response types
            if "sessionId" in result:
                self.session_id = result["sessionId"]
                print(f"   📝 Session ID: {self.session_id}")
            elif "agentInfo" in result:
                agent_info = result["agentInfo"]
                print(f"   Agent: {agent_info['name']} v{agent_info['version']}")

        elif "error" in response:
            error = response["error"]
            print(f"   ❌ Error (ID: {response.get('id', 'N/A')})")
            print(f"   Code: {error['code']}")
            print(f"   Message: {error['message']}")
            if "data" in error:
                print(f"   Data: {json.dumps(error['data'], indent=6)}")

        elif "method" in response:
            # Notification
            method = response["method"]
            print(f"   📢 Notification: {method}")
            if method == "session/update":
                update = response["params"]["update"]
                update_type = update.get("sessionUpdate", "unknown")
                print(f"   Type: {update_type}")
                if "content" in update and "text" in update["content"]:
                    text = update["content"]["text"]
                    # Truncate long text
                    if len(text) > 200:
                        print(f"   Text: {text[:200]}...")
                    else:
                        print(f"   Text: {text}")

        # Always show full JSON for reference (optional, can be commented out)
        # print(f"\n   Full JSON:")
        # print(json.dumps(response, indent=4))
        print()

    def send_message(self, message_dict):
        """Send a JSON-RPC message."""
        if not self.process or not self.process.stdin:
            print("❌ No active process")
            return

        message_json = json.dumps(message_dict)
        message_bytes = message_json.encode("utf-8")

        print(f"\n📤 Sending: {message_dict.get('method', 'notification')}")
        if message_dict.get("params"):
            print(f"   Params: {json.dumps(message_dict['params'], indent=4)}")

        self.process.stdin.write(message_bytes + b"\n")
        self.process.stdin.flush()

    def cmd_init(self, _args):
        """Send initialize request."""
        self.message_id += 1
        self.send_message(
            {
                "jsonrpc": "2.0",
                "id": self.message_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": 1,
                    "clientCapabilities": {
                        "fs": {"readTextFile": True, "writeTextFile": True},
                        "terminal": True,
                    },
                    "clientInfo": {
                        "name": "debug-client",
                        "title": "ACP Debug Client",
                        "version": "1.0.0",
                    },
                },
            }
        )

    def cmd_new(self, args):
        """Create a new session."""
        if not args:
            cwd = os.getcwd()
            print(f"Using current directory: {cwd}")
        else:
            cwd = args[0]
            if not Path(cwd).is_dir():
                print(f"❌ Not a directory: {cwd}")
                return

        self.message_id += 1
        self.send_message(
            {
                "jsonrpc": "2.0",
                "id": self.message_id,
                "method": "session/new",
                "params": {"cwd": cwd, "mcpServers": []},
            }
        )

    def cmd_load(self, args):
        """Load an existing session."""
        if not args:
            print("❌ Usage: load <sessionId>")
            return

        session_id = args[0]
        cwd = args[1] if len(args) > 1 else os.getcwd()

        self.message_id += 1
        self.send_message(
            {
                "jsonrpc": "2.0",
                "id": self.message_id,
                "method": "session/load",
                "params": {"sessionId": session_id, "cwd": cwd, "mcpServers": []},
            }
        )

    def cmd_prompt(self, args):
        """Send a prompt to the current session."""
        if not self.session_id:
            print("❌ No active session. Use 'new' or 'load' first.")
            return

        if not args:
            print("❌ Usage: prompt <message>")
            return

        message = " ".join(args)

        self.message_id += 1
        self.send_message(
            {
                "jsonrpc": "2.0",
                "id": self.message_id,
                "method": "prompt",
                "params": {
                    "sessionId": self.session_id,
                    "agentRequest": {
                        "role": "user",
                        "content": [{"type": "text", "text": message}],
                    },
                },
            }
        )

    def cmd_raw(self, args):
        """Send raw JSON-RPC message."""
        if not args:
            print("❌ Usage: raw <json>")
            return

        json_str = " ".join(args)
        try:
            message = json.loads(json_str)
            self.message_id += 1
            if "id" not in message:
                message["id"] = self.message_id
            self.send_message(message)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON: {e}")

    def stop(self):
        """Stop the server and cleanup."""
        print("\n\nShutting down...")
        self.running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        print("✅ Cleanup complete")


def main():
    """Main debug client loop."""
    print("🔧 OpenHands ACP Debug Client")
    print("=" * 70)
    print()
    print("Commands:")
    print("  init              - Send initialize request")
    print("  new [<cwd>]       - Create a new session")
    print("  load <sessionId>  - Load an existing session")
    print("  prompt <message>  - Send a prompt to current session")
    print("  raw <json>        - Send raw JSON-RPC message")
    print("  help              - Show this help")
    print("  quit              - Exit the debug client")
    print()
    print("=" * 70)
    print()

    client = ACPDebugClient()

    try:
        client.start_server()
        print()
        print("💡 TIP: Start with 'init' command to initialize the connection")
        print()

        # Interactive command loop
        while True:
            try:
                user_input = input("acp> ").strip()
                if not user_input:
                    continue

                parts = user_input.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1].split() if len(parts) > 1 else []

                if command == "quit" or command == "exit":
                    break
                elif command == "help":
                    print("\nCommands:")
                    print("  init              - Send initialize request")
                    print("  new [<cwd>]       - Create a new session")
                    print("                      (default: current directory)")
                    print("  load <sessionId>  - Load an existing session")
                    print("  prompt <message>  - Send a prompt to current session")
                    print("  raw <json>        - Send raw JSON-RPC message")
                    print("  help              - Show this help")
                    print("  quit              - Exit the debug client")
                    print()
                elif command == "init":
                    client.cmd_init(args)
                elif command == "new":
                    client.cmd_new(args)
                elif command == "load":
                    client.cmd_load(args)
                elif command == "prompt":
                    client.cmd_prompt(args)
                elif command == "raw":
                    client.cmd_raw(args)
                else:
                    print(f"❌ Unknown command: {command}")
                    print("   Type 'help' for available commands")

            except KeyboardInterrupt:
                print("\n\n👋 Exiting...")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

    finally:
        client.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
