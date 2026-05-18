"""CLI-level stop hook execution.

Stop hooks are stripped from the SDK's HookConfig and executed here, outside
the SDK's run-loop state lock.  This avoids two problems:

1. The SDK holds its FIFO lock while running stop hooks, which blocks pause().
2. A missing hook script causes Python to exit with code 2 — which the SDK
   interprets as "deny the stop", creating an infinite LLM-calling loop.

By running stop hooks at the CLI level we can:
- Keep the pause/ESC path responsive at all times.
- Treat execution errors (missing script, timeout, crash) as *allow stop*
  rather than *block stop*.
"""

import logging

from openhands.sdk.hooks import (
    HookConfig,
    HookDefinition,
    HookEvent,
    HookEventType,
    HookExecutor,
    HookMatcher,
    HookResult,
)


logger = logging.getLogger(__name__)


def _collect_hook_definitions(
    stop_matchers: list[HookMatcher],
) -> list[HookDefinition]:
    """Flatten stop matchers into a list of HookDefinitions that match."""
    config = HookConfig(stop=stop_matchers)
    return config.get_hooks_for_event(HookEventType.STOP)


def run_stop_hooks(
    *,
    stop_matchers: list[HookMatcher],
    session_id: str | None = None,
    working_dir: str | None = None,
) -> tuple[bool, str | None]:
    """Execute stop hooks outside the SDK run loop.

    Returns:
        (should_stop, feedback) — ``should_stop`` is True when the agent is
        allowed to finish.  ``feedback`` is optional text from the hook to
        feed back into the conversation if the stop is denied.

    Error handling differs from the SDK: execution failures (missing script,
    timeout, non-zero exit other than the "block" protocol code 2) are
    logged but treated as *allow stop*.  Only an explicit block (exit code 2
    with no execution error, or a JSON ``{"decision": "deny"}`` response)
    prevents stopping.
    """
    hooks = _collect_hook_definitions(stop_matchers)
    if not hooks:
        return True, None

    executor = HookExecutor(working_dir=working_dir)
    event = HookEvent(
        event_type=HookEventType.STOP,
        session_id=session_id,
        working_dir=working_dir,
        metadata={"reason": "agent_finished"},
    )

    results: list[HookResult] = []
    for hook in hooks:
        result = executor.execute(hook, event)
        results.append(result)

        if result.error:
            # Execution error (missing script, timeout, crash).
            # Treat as "allow stop" — don't let broken hooks block finishing.
            logger.warning(
                "Stop hook '%s' failed (exit_code=%s): %s — allowing stop",
                hook.command,
                result.exit_code,
                result.error,
            )
            continue

        if not result.success and result.exit_code == 2 and result.stderr:
            # Heuristic: if stderr contains "can't open file" or "No such file",
            # this is likely Python failing to find the script, not a deliberate
            # block signal.
            stderr_lower = result.stderr.lower()
            if "no such file" in stderr_lower or "can't open file" in stderr_lower:
                logger.warning(
                    "Stop hook '%s' appears to be a missing-script error "
                    "(exit_code=2, stderr=%r) — allowing stop",
                    hook.command,
                    result.stderr.strip(),
                )
                continue

        if result.blocked:
            # Genuine block — collect feedback and stop processing.
            feedback = _extract_feedback(result)
            logger.info("Stop hook '%s' denied stopping: %s", hook.command, feedback)
            return False, feedback

    return True, None


def _extract_feedback(result: HookResult) -> str | None:
    """Extract human-readable feedback from a blocking HookResult."""
    if result.additional_context:
        return result.additional_context
    if result.reason:
        return result.reason
    if result.stderr and result.stderr.strip():
        return result.stderr.strip()
    return "Blocked by stop hook"
