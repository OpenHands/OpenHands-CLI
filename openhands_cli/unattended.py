from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import signal
import uuid
from datetime import UTC, datetime
from enum import IntEnum
from pathlib import Path
from types import FrameType
from typing import Any

from rich.console import Console

from openhands.sdk import BaseConversation, Message, TextContent
from openhands.sdk.conversation.exceptions import ConversationRunError
from openhands.sdk.event.base import Event
from openhands.sdk.llm.exceptions import (
    LLMAuthenticationError,
    LLMBadRequestError,
    LLMContextWindowExceedError,
    LLMNoResponseError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from openhands.sdk.security.confirmation_policy import NeverConfirm
from openhands_cli.setup import setup_conversation
from openhands_cli.stores import MissingEnvironmentVariablesError


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE = 2
    CONFIGURATION = 3
    PROVIDER = 4
    AGENT = 5
    INTERNAL = 6


class JsonlEventStream:
    def __init__(self, output_dir: Path, *, append: bool = False) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / "events.jsonl"
        self._file = self.path.open("a" if append else "w", encoding="utf-8")

    def _emit(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        print(line, flush=True)
        self._file.write(line + "\n")
        self._file.flush()
        os.fsync(self._file.fileno())

    def emit_event(self, event: Event) -> None:
        self._emit({"type": "event", "event": json.loads(event.model_dump_json())})

    def emit_lifecycle(self, event_type: str, **fields: Any) -> None:
        self._emit({"type": event_type, **fields})

    def close(self) -> None:
        self._file.close()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def validate_run_paths(
    workspace: Path, output_dir: Path, *, allow_existing: bool = False
) -> tuple[Path, Path]:
    workspace = workspace.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not workspace.exists():
        raise ValueError(f"Workspace does not exist: {workspace}")
    if not workspace.is_dir():
        raise ValueError(f"Workspace is not a directory: {workspace}")
    if not os.access(workspace, os.W_OK | os.X_OK):
        raise ValueError(f"Workspace is not writable: {workspace}")
    if not allow_existing:
        for filename in ("events.jsonl", "run.json"):
            if (output_dir / filename).exists():
                raise ValueError(
                    f"Output directory already contains {filename}: {output_dir}"
                )
    return workspace, output_dir


_PROVIDER_MODULES = ("anthropic", "httpcore", "httpx", "litellm", "openai")
_PROVIDER_ERRORS = (
    LLMAuthenticationError,
    LLMBadRequestError,
    LLMContextWindowExceedError,
    LLMNoResponseError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)


def classify_run_error(error: BaseException) -> ExitCode:
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, _PROVIDER_ERRORS):
            return ExitCode.PROVIDER
        module = type(current).__module__.split(".", 1)[0]
        if module in _PROVIDER_MODULES:
            return ExitCode.PROVIDER
        current = current.__cause__ or current.__context__
    return ExitCode.AGENT


def _safe_error_message(error: BaseException) -> str:
    message = str(error)
    for name in ("LLM_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        value = os.environ.get(name)
        if value:
            message = message.replace(value, "[REDACTED]")
    return message[:2000]


def _write_summary(output_dir: Path, summary: dict[str, Any]) -> None:
    target = output_dir / "run.json"
    temporary = output_dir / ".run.json.tmp"
    temporary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, target)


def _task_from_args(args: argparse.Namespace) -> str:
    if args.task is not None:
        return args.task
    try:
        return args.file.expanduser().read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Unable to read task file {args.file}: {error}") from error


def _run_worker(args: argparse.Namespace) -> int:
    started_at = utc_now()
    output_dir = args.output_dir.expanduser().resolve()
    stream: JsonlEventStream | None = None
    conversation: BaseConversation | None = None
    received_signal: int | None = None
    previous_environment: dict[str, str | None] = {}
    previous_handlers: dict[int, Any] = {}
    summary: dict[str, Any] = {
        "status": "internal_error",
        "exit_code": int(ExitCode.INTERNAL),
        "started_at": started_at,
    }

    def handle_signal(signum: int, _frame: FrameType | None) -> None:
        nonlocal received_signal
        received_signal = signum
        if stream is not None:
            stream.emit_lifecycle("run.interrupt_requested", signal=signum)
        if conversation is not None:
            conversation.interrupt()

    try:
        workspace, output_dir = validate_run_paths(
            args.workspace, args.output_dir, allow_existing=True
        )
        task = _task_from_args(args)
        if not task.strip():
            raise ValueError("Task must not be empty")

        output_dir.mkdir(parents=True, exist_ok=True)
        stream = JsonlEventStream(output_dir)
        conversation_id = args.conversation_id
        summary.update(
            {
                "conversation_id": conversation_id.hex,
                "workspace": str(workspace),
                "output_dir": str(output_dir),
            }
        )
        stream.emit_lifecycle(
            "run.started",
            conversation_id=conversation_id.hex,
            workspace=str(workspace),
        )

        environment = {
            "OPENHANDS_WORK_DIR": str(workspace),
            "OPENHANDS_PERSISTENCE_DIR": str(output_dir / "state"),
            "OPENHANDS_CONVERSATIONS_DIR": str(output_dir / "conversations"),
        }
        for name, value in environment.items():
            previous_environment[name] = os.environ.get(name)
            os.environ[name] = value

        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, handle_signal)

        load_public_skills = args.load_public_skills and not args.offline
        conversation = setup_conversation(
            conversation_id,
            confirmation_policy=NeverConfirm(),
            event_callback=stream.emit_event,
            console=Console(stderr=True, highlight=False),
            env_overrides_enabled=True,
            critic_disabled=True,
            ignore_persisted_agent=True,
            load_user_skills=args.load_user_skills,
            load_public_skills=load_public_skills,
            llm_timeout=args.llm_timeout,
            llm_num_retries=args.llm_retries,
        )
        conversation.send_message(
            Message(role="user", content=[TextContent(text=task)])
        )
        conversation.run()

        if received_signal is not None:
            exit_code = 128 + received_signal
            summary.update(
                {
                    "status": "interrupted",
                    "exit_code": exit_code,
                    "signal": received_signal,
                }
            )
            stream.emit_lifecycle(
                "run.interrupted", exit_code=exit_code, signal=received_signal
            )
            return exit_code

        summary.update({"status": "completed", "exit_code": int(ExitCode.SUCCESS)})
        stream.emit_lifecycle("run.completed", exit_code=int(ExitCode.SUCCESS))
        return int(ExitCode.SUCCESS)
    except (MissingEnvironmentVariablesError, ValueError) as error:
        summary.update(
            {
                "status": "configuration_error",
                "exit_code": int(ExitCode.CONFIGURATION),
                "error_type": type(error).__name__,
                "error_message": _safe_error_message(error),
            }
        )
        if stream is not None:
            stream.emit_lifecycle(
                "run.failed",
                exit_code=int(ExitCode.CONFIGURATION),
                error_category="configuration",
                error_type=type(error).__name__,
            )
        return int(ExitCode.CONFIGURATION)
    except ConversationRunError as error:
        exit_code = classify_run_error(error.original_exception)
        category = "provider" if exit_code == ExitCode.PROVIDER else "agent"
        summary.update(
            {
                "status": f"{category}_error",
                "exit_code": int(exit_code),
                "error_type": type(error.original_exception).__name__,
                "error_message": _safe_error_message(error.original_exception),
            }
        )
        if stream is not None:
            stream.emit_lifecycle(
                "run.failed",
                exit_code=int(exit_code),
                error_category=category,
                error_type=type(error.original_exception).__name__,
            )
        return int(exit_code)
    except Exception as error:
        summary.update(
            {
                "status": "internal_error",
                "exit_code": int(ExitCode.INTERNAL),
                "error_type": type(error).__name__,
                "error_message": _safe_error_message(error),
            }
        )
        if stream is not None:
            stream.emit_lifecycle(
                "run.failed",
                exit_code=int(ExitCode.INTERNAL),
                error_category="internal",
                error_type=type(error).__name__,
            )
        return int(ExitCode.INTERNAL)
    finally:
        summary["finished_at"] = utc_now()
        if conversation is not None:
            conversation.close()
        if output_dir.exists():
            _write_summary(output_dir, summary)
        if stream is not None:
            stream.close()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        for name, value in previous_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _worker_entry(args: argparse.Namespace) -> None:
    raise SystemExit(_run_worker(args))


def run_unattended(args: argparse.Namespace) -> int:
    try:
        workspace, output_dir = validate_run_paths(args.workspace, args.output_dir)
        task = _task_from_args(args)
        if not task.strip():
            raise ValueError("Task must not be empty")
    except ValueError as error:
        output_dir = args.output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "status": "configuration_error",
            "exit_code": int(ExitCode.CONFIGURATION),
            "started_at": utc_now(),
            "finished_at": utc_now(),
            "error_type": type(error).__name__,
            "error_message": _safe_error_message(error),
        }
        _write_summary(output_dir, summary)
        return int(ExitCode.CONFIGURATION)

    args.workspace = workspace
    args.output_dir = output_dir
    args.task = task
    args.file = None
    args.conversation_id = uuid.uuid4()
    started_at = utc_now()
    running_summary = {
        "status": "running",
        "exit_code": None,
        "started_at": started_at,
        "conversation_id": args.conversation_id.hex,
        "workspace": str(workspace),
        "output_dir": str(output_dir),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_summary(output_dir, running_summary)

    context = multiprocessing.get_context("spawn")
    process = context.Process(target=_worker_entry, args=(args,))
    received_signal: int | None = None
    previous_handlers: dict[int, Any] = {}

    def handle_signal(signum: int, _frame: FrameType | None) -> None:
        nonlocal received_signal
        received_signal = signum
        if process.is_alive():
            process.terminate()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, handle_signal)

    try:
        process.start()
        while process.is_alive():
            process.join(timeout=0.1)
            if received_signal is not None:
                process.join(timeout=3)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=3)
                break

        if received_signal is not None:
            exit_code = 128 + received_signal
            summary = {
                **running_summary,
                "status": "interrupted",
                "exit_code": exit_code,
                "signal": received_signal,
                "finished_at": utc_now(),
            }
            stream = JsonlEventStream(output_dir, append=True)
            stream.emit_lifecycle(
                "run.interrupted", exit_code=exit_code, signal=received_signal
            )
            stream.close()
            _write_summary(output_dir, summary)
            return exit_code

        if process.exitcode is None:
            exit_code = int(ExitCode.INTERNAL)
        elif process.exitcode < 0 or process.exitcode > int(ExitCode.INTERNAL):
            exit_code = int(ExitCode.INTERNAL)
        else:
            exit_code = process.exitcode

        if exit_code == int(ExitCode.INTERNAL):
            current_summary = json.loads((output_dir / "run.json").read_text())
            if current_summary.get("status") == "running":
                current_summary.update(
                    {
                        "status": "internal_error",
                        "exit_code": exit_code,
                        "finished_at": utc_now(),
                        "error_type": "WorkerProcessError",
                        "error_message": (
                            f"Agent worker exited with code {process.exitcode}"
                        ),
                    }
                )
                _write_summary(output_dir, current_summary)
        return exit_code
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
