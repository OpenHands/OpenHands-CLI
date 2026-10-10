import json
from pathlib import Path

import httpx
import pytest

from openhands.sdk import Message
from openhands.sdk.event import MessageEvent
from openhands.sdk.llm.exceptions import LLMAuthenticationError
from openhands_cli.argparsers.main_parser import create_main_parser
from openhands_cli.unattended import (
    ExitCode,
    JsonlEventStream,
    classify_run_error,
    validate_run_paths,
)


def test_run_parser_exposes_unattended_contract(tmp_path: Path):
    parser = create_main_parser()
    workspace = tmp_path / "workspace"
    output = tmp_path / "output"
    workspace.mkdir()

    args = parser.parse_args(
        [
            "run",
            "--task",
            "Fix the bug",
            "--workspace",
            str(workspace),
            "--output-dir",
            str(output),
            "--offline",
            "--no-user-skills",
            "--llm-timeout",
            "60",
            "--llm-retries",
            "2",
        ]
    )

    assert args.command == "run"
    assert args.task == "Fix the bug"
    assert args.workspace == workspace
    assert args.output_dir == output
    assert args.offline is True
    assert args.load_user_skills is False
    assert args.llm_timeout == 60
    assert args.llm_retries == 2


def test_run_parser_requires_exactly_one_task_source(tmp_path: Path):
    parser = create_main_parser()
    common = [
        "run",
        "--workspace",
        str(tmp_path),
        "--output-dir",
        str(tmp_path / "output"),
    ]

    with pytest.raises(SystemExit) as missing:
        parser.parse_args(common)
    assert missing.value.code == ExitCode.USAGE

    with pytest.raises(SystemExit) as duplicate:
        parser.parse_args(common + ["--task", "one", "--file", "task.txt"])
    assert duplicate.value.code == ExitCode.USAGE


def test_validate_run_paths_rejects_missing_workspace(tmp_path: Path):
    with pytest.raises(ValueError, match="Workspace does not exist"):
        validate_run_paths(tmp_path / "missing", tmp_path / "output")


def test_jsonl_event_stream_flushes_stdout_and_artifact(tmp_path: Path, capsys):
    stream = JsonlEventStream(tmp_path)
    event = MessageEvent(source="agent", llm_message=Message(role="assistant"))

    stream.emit_event(event)
    stream.emit_lifecycle("run.completed", exit_code=0)
    stream.close()

    stdout_lines = capsys.readouterr().out.splitlines()
    artifact_lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert stdout_lines == artifact_lines
    assert json.loads(stdout_lines[0])["type"] == "event"
    assert json.loads(stdout_lines[1]) == {
        "type": "run.completed",
        "exit_code": 0,
    }


def test_classify_run_error_distinguishes_provider_and_agent_failures():
    provider_error = httpx.HTTPError("provider failed")

    assert classify_run_error(provider_error) == ExitCode.PROVIDER
    assert classify_run_error(LLMAuthenticationError()) == ExitCode.PROVIDER
    assert classify_run_error(RuntimeError("agent loop failed")) == ExitCode.AGENT
