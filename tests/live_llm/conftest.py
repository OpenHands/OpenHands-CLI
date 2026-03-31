"""Fixtures and configuration for live LLM integration tests.

These tests execute the real CLI binary (via ``uv run openhands``) against a
real LLM provider in ``--headless`` mode.  They are **opt-in**: pass
``--run-live-llm`` to ``pytest`` to enable them.

Required environment variables (when enabled):
    LLM_API_KEY   – API key for the LLM provider
    LLM_MODEL     – Model identifier (e.g. ``anthropic/claude-sonnet-4-5-20250929``)

Optional:
    LLM_BASE_URL  – Custom base URL (e.g. a LiteLLM proxy)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Pytest option
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("live_llm", "Live LLM integration tests")
    group.addoption(
        "--run-live-llm",
        action="store_true",
        default=False,
        help="Execute live LLM integration tests (requires LLM_API_KEY and LLM_MODEL).",
    )
    group.addoption(
        "--live-llm-results-dir",
        action="store",
        default=None,
        help=(
            "Directory to store per-test JSON result files "
            "(default: .live-llm-results)."
        ),
    )


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def live_llm_enabled(pytestconfig: pytest.Config) -> bool:
    return bool(pytestconfig.getoption("--run-live-llm"))


@pytest.fixture(scope="session")
def live_llm_results_dir(pytestconfig: pytest.Config) -> Path:
    configured = pytestconfig.getoption("--live-llm-results-dir")
    result_dir = Path(configured) if configured else REPO_ROOT / ".live-llm-results"
    result_dir.mkdir(parents=True, exist_ok=True)
    # Clean previous results on the controller (not on xdist workers)
    if not hasattr(pytestconfig, "workerinput"):
        for existing in result_dir.glob("*.json"):
            existing.unlink()
    return result_dir


@pytest.fixture(scope="session")
def llm_env() -> dict[str, str]:
    """Return validated LLM environment variables."""
    api_key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")
    base_url = os.environ.get("LLM_BASE_URL", "")
    return {
        "LLM_API_KEY": api_key,
        "LLM_MODEL": model,
        "LLM_BASE_URL": base_url,
    }


# ---------------------------------------------------------------------------
# Per-test fixture: runs the CLI headless
# ---------------------------------------------------------------------------

# Maximum wall-clock time for a single CLI invocation
CLI_TIMEOUT_SECONDS = int(os.environ.get("LIVE_LLM_TIMEOUT", "300"))  # 5 min


@dataclass
class CLIResult:
    """Result of running the CLI in headless mode."""

    task: str
    stdout: str
    stderr: str
    returncode: int
    duration_seconds: float
    timed_out: bool = False
    work_dir: str = ""
    env_snapshot: dict[str, str] = field(default_factory=dict)

    @property
    def output(self) -> str:
        """Combined stdout + stderr for assertion convenience."""
        return self.stdout + "\n" + self.stderr


def _run_cli_headless(
    task: str,
    *,
    llm_env: dict[str, str],
    work_dir: Path,
    timeout: int = CLI_TIMEOUT_SECONDS,
) -> CLIResult:
    """Run ``uv run openhands --headless --task '...' --override-with-envs``."""
    env = os.environ.copy()
    env.update({k: v for k, v in llm_env.items() if v})
    # Force the working directory so tools operate in a scratch space
    env["OPENHANDS_WORK_DIR"] = str(work_dir)

    cmd = [
        sys.executable,
        "-m",
        "openhands_cli.entrypoint",
        "--headless",
        "--always-approve",
        "--override-with-envs",
        "--task",
        task,
    ]

    start = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        raw_out = exc.stdout
        raw_err = exc.stderr
        stdout = raw_out.decode() if isinstance(raw_out, bytes) else (raw_out or "")
        stderr = raw_err.decode() if isinstance(raw_err, bytes) else (raw_err or "")
        returncode = -1

    duration = time.perf_counter() - start

    return CLIResult(
        task=task,
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        duration_seconds=duration,
        timed_out=timed_out,
        work_dir=str(work_dir),
        env_snapshot={k: ("***" if "KEY" in k else v) for k, v in llm_env.items()},
    )


@pytest.fixture
def run_cli(
    live_llm_enabled: bool,
    llm_env: dict[str, str],
    live_llm_results_dir: Path,
    tmp_path: Path,
    request: pytest.FixtureRequest,
):
    """Fixture that provides a callable to run the CLI with a given task.

    Usage::

        def test_something(run_cli):
            result = run_cli("echo hello")
            assert "hello" in result.output
    """
    if not live_llm_enabled:
        pytest.skip("Use --run-live-llm to execute live LLM integration tests.")

    api_key = llm_env.get("LLM_API_KEY", "")
    model = llm_env.get("LLM_MODEL", "")
    if not api_key or not model:
        pytest.skip(
            "LLM_API_KEY and LLM_MODEL environment variables are required "
            "for live LLM tests."
        )

    # Each test gets its own scratch workspace
    work_dir = tmp_path / "workspace"
    work_dir.mkdir()

    results: list[CLIResult] = []

    def _invoke(task: str, *, timeout: int = CLI_TIMEOUT_SECONDS) -> CLIResult:
        result = _run_cli_headless(
            task, llm_env=llm_env, work_dir=work_dir, timeout=timeout
        )
        results.append(result)
        return result

    yield _invoke

    # Write JSON result file for CI reporting
    for i, result in enumerate(results):
        test_id = request.node.nodeid.replace("/", "__").replace("::", "__")
        suffix = f"__{i}" if len(results) > 1 else ""
        result_file = live_llm_results_dir / f"{test_id}{suffix}.json"
        payload = {
            "test": request.node.nodeid,
            "task": result.task,
            "status": (
                "passed"
                if result.returncode == 0 and not result.timed_out
                else "failed"
            ),
            "duration_seconds": result.duration_seconds,
            "returncode": result.returncode,
            "timed_out": result.timed_out,
            "stdout_tail": result.stdout[-2000:] if result.stdout else "",
            "stderr_tail": result.stderr[-2000:] if result.stderr else "",
        }
        result_file.write_text(json.dumps(payload, indent=2))
