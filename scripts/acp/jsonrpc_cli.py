#!/usr/bin/env python3
"""
Interactive JSON-RPC CLI for testing the CLI binary executable
for Agent Client Protocol (ACP).
Sends JSON-RPC messages to the child process stdin and prints responses
from stdout and stderr.

uv run python scripts/acp/jsonrpc_cli.py ./dist/openhands acp
"""

import argparse
import asyncio
import json
import sys


async def stream_output(stream: asyncio.StreamReader, prefix: str):
    """Continuously read from a stream and print lines with a prefix."""
    while True:
        line = await stream.readline()
        if not line:
            break

        text = line.decode(errors="replace").rstrip("\n")
        print(f"{prefix} {text}")

        # If it's JSON, also pretty-print it
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            continue

        pretty = json.dumps(obj, indent=2, ensure_ascii=False)
        print(f"{prefix} (pretty)\n{pretty}")


async def stdin_loop(proc: asyncio.subprocess.Process):
    """
    Read lines from the user and send them to the child process stdin.

    Commands:
      :q, :quit, :exit  -> terminate the child and exit
    """
    loop = asyncio.get_running_loop()

    print("Type JSON-RPC messages as single lines.")
    print("Commands: :q / :quit / :exit to stop.")
    print()

    while True:
        # Use a thread so stdin reading doesn't block the event loop
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            # EOF on stdin
            break

        line = line.rstrip("\n")
        if not line:
            continue

        if line in (":q", ":quit", ":exit"):
            print("Exiting: terminating child process...")
            proc.terminate()
            break

        data = (line + "\n").encode()
        try:
            if proc.stdin is None:
                print("Child stdin is closed; cannot send more data.")
                break

            proc.stdin.write(data)
            await proc.stdin.drain()

            # ✅ Confirmation that the data was sent to the child process
            print(f"[sent] {line}")

        except BrokenPipeError:
            print("Broken pipe: child process no longer accepts input.")
            break


async def run(binary: str, args: list[str]):
    print(f"Starting child process: {binary} {' '.join(args)}")
    proc = await asyncio.create_subprocess_exec(
        binary,
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    print(f"Child PID: {proc.pid}")
    print("-" * 60)

    stdout_task = asyncio.create_task(
        stream_output(proc.stdout, "[stdout]")  # type: ignore[arg-type]
    )
    stderr_task = asyncio.create_task(
        stream_output(proc.stderr, "[stderr]")  # type: ignore[arg-type]
    )

    try:
        await stdin_loop(proc)
    finally:
        if proc.returncode is None:
            proc.terminate()
        await proc.wait()

        stdout_task.cancel()
        stderr_task.cancel()

        print("-" * 60)
        print(f"Child exited with return code {proc.returncode}")


def main():
    parser = argparse.ArgumentParser(
        description="Interactive JSON-RPC CLI for testing a binary."
    )
    parser.add_argument(
        "binary",
        help="Path to the JSON-RPC-speaking binary (e.g., ./dist/openhands)",
    )
    parser.add_argument(
        "binary_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments to pass to the binary (e.g., acp).",
    )

    args = parser.parse_args()

    try:
        asyncio.run(run(args.binary, args.binary_args))
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)


if __name__ == "__main__":
    main()
