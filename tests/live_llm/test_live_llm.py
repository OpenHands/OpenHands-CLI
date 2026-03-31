"""Live LLM integration tests.

Each test sends a prompt to the real CLI in ``--headless`` mode with a live
LLM provider.  Assertions are intentionally **relaxed** — we check for
behavioral keywords rather than exact output, because LLM responses are
non-deterministic.

Enable with ``--run-live-llm`` and set ``LLM_API_KEY`` / ``LLM_MODEL``.

Test design rationale
---------------------
The three tests below are chosen to maximise component coverage with
minimal LLM calls:

1. **test_echo_command** — smoke test for the entire pipeline:
   LLM connectivity → tool-call generation → terminal execution →
   observation capture → agent summary.

2. **test_file_create_and_read** — validates multi-step tool chaining:
   the agent must plan two sequential operations (write then read) and
   return the file contents.

3. **test_python_code_generation_and_execution** — exercises code
   generation, file creation (via either terminal or file_editor tool),
   and Python execution in a single turn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from tests.live_llm.conftest import CLIResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_cli_success(result: CLIResult) -> None:
    """Common assertions: no timeout, process exited cleanly."""
    assert not result.timed_out, (
        f"CLI timed out after {result.duration_seconds:.0f}s.\n"
        f"stdout tail: {result.stdout[-500:]}\n"
        f"stderr tail: {result.stderr[-500:]}"
    )
    assert result.returncode == 0, (
        f"CLI exited with code {result.returncode}.\n"
        f"stdout tail: {result.stdout[-1000:]}\n"
        f"stderr tail: {result.stderr[-1000:]}"
    )


def _output_contains_any(output: str, keywords: list[str]) -> bool:
    """Check whether *output* contains at least one of *keywords* (case-insensitive)."""
    lower = output.lower()
    return any(kw.lower() in lower for kw in keywords)


# ---------------------------------------------------------------------------
# Test 1 — basic terminal command (smoke test)
# ---------------------------------------------------------------------------
# Components exercised:
#   LLM connectivity, tool-call parsing, TerminalTool, observation routing,
#   agent response generation, headless summary output, --override-with-envs.


class TestEchoCommand:
    """Verify the agent can execute a trivial terminal command."""

    def test_echo_command(self, run_cli):
        result: CLIResult = run_cli(
            "Run this exact terminal command and show me the output: "
            "echo 'hello from openhands'"
        )
        _assert_cli_success(result)

        # The agent must have executed `echo` — the literal string should
        # appear somewhere in the captured output (terminal observation or
        # agent summary).
        assert _output_contains_any(result.output, ["hello from openhands"]), (
            "Expected 'hello from openhands' in CLI output.\n"
            f"stdout tail:\n{result.stdout[-1000:]}"
        )


# ---------------------------------------------------------------------------
# Test 2 — multi-step file create + read
# ---------------------------------------------------------------------------
# Components exercised:
#   Multi-turn tool chain (write → read), file system operations via
#   TerminalTool or FileEditorTool, observation correctness across turns,
#   agent planning / sequencing.


class TestFileCreateAndRead:
    """Verify the agent can create a file and read it back."""

    SENTINEL = "live-llm-integration-test-ok"

    def test_file_create_and_read(self, run_cli):
        result: CLIResult = run_cli(
            f"Create a file called 'check.txt' containing exactly the text "
            f"'{self.SENTINEL}', then read it back with cat and show me the output."
        )
        _assert_cli_success(result)

        assert _output_contains_any(result.output, [self.SENTINEL]), (
            f"Expected '{self.SENTINEL}' in CLI output.\n"
            f"stdout tail:\n{result.stdout[-1000:]}"
        )


# ---------------------------------------------------------------------------
# Test 3 — code generation + execution
# ---------------------------------------------------------------------------
# Components exercised:
#   Code generation quality, file creation (file_editor or terminal),
#   Python subprocess execution via TerminalTool, numeric output parsing,
#   end-to-end multi-step flow.


class TestCodeGenAndExecution:
    """Verify the agent can write and run a Python script."""

    def test_python_code_gen_and_run(self, run_cli):
        result: CLIResult = run_cli(
            "Write a Python script called calc.py that prints the result of 2**10, "
            "then run it with python3 and show me the output."
        )
        _assert_cli_success(result)

        # 2**10 == 1024 — should appear in agent output or terminal observation
        assert _output_contains_any(result.output, ["1024"]), (
            "Expected '1024' (2**10) in CLI output.\n"
            f"stdout tail:\n{result.stdout[-1000:]}"
        )
