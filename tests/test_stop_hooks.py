"""Tests for stop hook handling to prevent conversation stalls.

Reproduces the bug described in https://github.com/OpenHands/OpenHands-CLI/issues/649:
When a Stop hook is configured, the conversation can stall in "Working" state after
FinishAction because:
1. Python exit code 2 (file not found) is treated as "block" by the hook executor,
   causing an infinite loop in the SDK run loop.
2. Stop hooks run while holding the SDK state lock, preventing pause() from working.

The fix strips stop hooks from HookConfig before passing to the SDK, and runs them
at the CLI level after conversation.run() returns.
"""

import json
import os
import stat
import subprocess
import time
import uuid
from unittest import mock

from openhands.sdk.hooks import HookConfig
from openhands.sdk.hooks.config import HookDefinition, HookMatcher
from openhands.sdk.hooks.executor import HookExecutor
from openhands.sdk.hooks.manager import HookManager
from openhands.sdk.hooks.types import HookEventType


class TestPythonExitCode2CausesBlock:
    """Test that Python exit code 2 (file not found) causes hook to report blocked.

    This is the root cause of the infinite loop: the hook executor treats exit
    code 2 as 'block the operation', but Python uses exit code 2 for file-not-found.
    """

    def test_python_missing_file_exits_with_code_2(self, tmp_path):
        """Verify Python exits with code 2 when script file doesn't exist."""
        result = subprocess.run(
            ["python3", str(tmp_path / "nonexistent.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2, (
            f"Expected exit code 2 for missing file, got {result.returncode}"
        )

    def test_hook_executor_treats_exit_code_2_as_blocked(self, tmp_path):
        """Verify the hook executor treats exit code 2 as a blocked operation."""
        hook = HookDefinition(
            command=f"python3 {tmp_path / 'nonexistent.py'}",
            timeout=5,
        )
        executor = HookExecutor(working_dir=str(tmp_path))
        from openhands.sdk.hooks.types import HookEvent

        event = HookEvent(
            event_type=HookEventType.STOP,
            session_id="test",
            working_dir=str(tmp_path),
        )
        result = executor.execute(hook, event)
        assert result.blocked is True, (
            "Exit code 2 should be treated as 'blocked' by hook executor"
        )
        assert result.should_continue is False

    def test_stop_hook_with_missing_script_denies_stop(self, tmp_path):
        """Test that a stop hook pointing to a missing script denies the stop.

        This is the exact scenario causing the infinite loop: the user configures
        a stop hook with a Python script that doesn't exist, causing Python to exit
        with code 2, which the SDK interprets as 'deny the stop'.
        """
        hook_config = HookConfig(
            stop=[
                HookMatcher(
                    matcher="*",
                    hooks=[
                        HookDefinition(
                            command=f"python3 {tmp_path / 'missing_hook.py'}",
                            timeout=5,
                        )
                    ],
                )
            ]
        )
        manager = HookManager(config=hook_config, working_dir=str(tmp_path))
        should_stop, results = manager.run_stop(reason="agent_finished")
        assert should_stop is False, (
            "Stop hook with missing script should deny the stop (exit code 2 = block)"
        )
        assert len(results) == 1
        assert results[0].blocked is True

    def test_stop_hook_with_working_script_allows_stop(self, tmp_path):
        """Test that a stop hook with a working script allows the stop."""
        script = tmp_path / "notify.py"
        script.write_text("print('notification sent')")

        hook_config = HookConfig(
            stop=[
                HookMatcher(
                    matcher="*",
                    hooks=[
                        HookDefinition(
                            command=f"python3 {script}",
                            timeout=5,
                        )
                    ],
                )
            ]
        )
        manager = HookManager(config=hook_config, working_dir=str(tmp_path))
        should_stop, results = manager.run_stop(reason="agent_finished")
        assert should_stop is True, (
            "Stop hook with working script should allow the stop"
        )
        assert len(results) == 1
        assert results[0].blocked is False
        assert results[0].success is True


class TestStopHookStripping:
    """Test that stop hooks are stripped from HookConfig before passing to SDK.

    The fix: strip stop hooks from the config passed to the SDK's Conversation,
    then handle them at the CLI level after conversation.run() returns.
    """

    def test_strip_stop_hooks_from_config(self):
        """Test the strip_stop_hooks utility function."""
        from openhands_cli.setup import strip_stop_hooks

        config = HookConfig(
            pre_tool_use=[
                HookMatcher(
                    matcher="terminal",
                    hooks=[HookDefinition(command="echo pre")],
                )
            ],
            stop=[
                HookMatcher(
                    matcher="*",
                    hooks=[HookDefinition(command="python notify.py")],
                )
            ],
        )

        stripped, stop_hooks = strip_stop_hooks(config)
        assert len(stripped.stop) == 0, "Stop hooks should be stripped"
        assert len(stripped.pre_tool_use) == 1, "Other hooks should be preserved"
        assert len(stop_hooks) == 1, "Stop hooks should be returned separately"

    def test_strip_stop_hooks_no_stop_hooks(self):
        """Test strip_stop_hooks when there are no stop hooks."""
        from openhands_cli.setup import strip_stop_hooks

        config = HookConfig(
            pre_tool_use=[
                HookMatcher(
                    matcher="*",
                    hooks=[HookDefinition(command="echo test")],
                )
            ],
        )

        stripped, stop_hooks = strip_stop_hooks(config)
        assert len(stripped.pre_tool_use) == 1
        assert len(stripped.stop) == 0
        assert len(stop_hooks) == 0

    def test_strip_stop_hooks_empty_config(self):
        """Test strip_stop_hooks with empty config."""
        from openhands_cli.setup import strip_stop_hooks

        config = HookConfig()
        stripped, stop_hooks = strip_stop_hooks(config)
        assert stripped.is_empty()
        assert len(stop_hooks) == 0

    def test_strip_stop_hooks_preserves_all_other_hook_types(self):
        """Test that all non-stop hook types are preserved."""
        from openhands_cli.setup import strip_stop_hooks

        config = HookConfig(
            pre_tool_use=[HookMatcher(hooks=[HookDefinition(command="echo pre")])],
            post_tool_use=[HookMatcher(hooks=[HookDefinition(command="echo post")])],
            user_prompt_submit=[
                HookMatcher(hooks=[HookDefinition(command="echo prompt")])
            ],
            session_start=[HookMatcher(hooks=[HookDefinition(command="echo start")])],
            session_end=[HookMatcher(hooks=[HookDefinition(command="echo end")])],
            stop=[HookMatcher(hooks=[HookDefinition(command="echo stop")])],
        )

        stripped, stop_hooks = strip_stop_hooks(config)
        assert len(stripped.pre_tool_use) == 1
        assert len(stripped.post_tool_use) == 1
        assert len(stripped.user_prompt_submit) == 1
        assert len(stripped.session_start) == 1
        assert len(stripped.session_end) == 1
        assert len(stripped.stop) == 0
        assert len(stop_hooks) == 1


class TestConversationRunnerStopHookHandling:
    """Test that ConversationRunner handles stop hooks after conversation.run().

    After the fix, stop hooks are run by the CLI after conversation.run() returns,
    not inside the SDK's run loop. This prevents:
    1. State lock being held during hook execution
    2. Infinite loops from failed hooks
    """

    def test_stop_hooks_run_after_conversation_finishes(self, tmp_path):
        """Test that stop hooks are executed after conversation.run() returns."""
        marker_file = tmp_path / "hook_ran"
        script = tmp_path / "stop_hook.sh"
        script.write_text(f"#!/bin/sh\ntouch {marker_file}\n")
        os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)

        stop_matchers = [
            HookMatcher(
                matcher="*",
                hooks=[HookDefinition(command=str(script), timeout=5)],
            )
        ]

        from openhands_cli.setup import run_stop_hooks

        run_stop_hooks(
            stop_matchers=stop_matchers,
            working_dir=str(tmp_path),
            session_id="test-session",
        )
        assert marker_file.exists(), "Stop hook script should have been executed"

    def test_failed_stop_hook_does_not_raise(self, tmp_path):
        """Test that a failed stop hook doesn't raise an exception.

        Failed stop hooks should be logged but not prevent the conversation
        from being marked as finished.
        """
        stop_matchers = [
            HookMatcher(
                matcher="*",
                hooks=[
                    HookDefinition(
                        command=f"python3 {tmp_path / 'nonexistent.py'}",
                        timeout=5,
                    )
                ],
            )
        ]

        from openhands_cli.setup import run_stop_hooks

        # Should not raise
        run_stop_hooks(
            stop_matchers=stop_matchers,
            working_dir=str(tmp_path),
            session_id="test-session",
        )

    def test_stop_hook_timeout_does_not_block(self, tmp_path):
        """Test that a slow stop hook respects timeout and doesn't block."""
        script = tmp_path / "slow_hook.sh"
        script.write_text("#!/bin/sh\nsleep 60\n")
        os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)

        stop_matchers = [
            HookMatcher(
                matcher="*",
                hooks=[HookDefinition(command=str(script), timeout=2)],
            )
        ]

        from openhands_cli.setup import run_stop_hooks

        start = time.time()
        run_stop_hooks(
            stop_matchers=stop_matchers,
            working_dir=str(tmp_path),
            session_id="test-session",
        )
        elapsed = time.time() - start
        assert elapsed < 10, (
            f"Stop hook should have timed out within "
            f"timeout+buffer, took {elapsed:.1f}s"
        )


class TestSetupConversationStripsStopHooks:
    """Test that setup_conversation strips stop hooks before passing to SDK."""

    def test_setup_conversation_does_not_pass_stop_hooks_to_sdk(
        self, mock_locations, persisted_agent, tmp_path
    ):
        """Verify stop hooks are stripped from HookConfig before SDK gets them."""
        hooks_dir = mock_locations.home_dir / ".openhands"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hooks_file = hooks_dir / "hooks.json"
        hooks_file.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "command": "python notify.py",
                                        "timeout": 30,
                                    }
                                ],
                            }
                        ],
                        "PreToolUse": [
                            {
                                "matcher": "terminal",
                                "hooks": [
                                    {
                                        "command": "echo pre-check",
                                        "timeout": 10,
                                    }
                                ],
                            }
                        ],
                    }
                }
            )
        )

        with (
            mock.patch("openhands_cli.setup.Conversation") as mock_conversation_cls,
            mock.patch(
                "openhands_cli.setup.load_agent_specs", return_value=persisted_agent
            ),
        ):
            mock_conversation_cls.return_value = mock.MagicMock()

            from openhands_cli.setup import setup_conversation

            setup_conversation(
                conversation_id=uuid.uuid4(),
                confirmation_policy=mock.MagicMock(),
            )

            # Verify that Conversation was called with a hook_config
            # that does NOT contain stop hooks
            call_kwargs = mock_conversation_cls.call_args
            hook_config_passed = call_kwargs.kwargs.get("hook_config") or call_kwargs[
                1
            ].get("hook_config")

            if hook_config_passed is not None:
                assert len(hook_config_passed.stop) == 0, (
                    "Stop hooks should be stripped before passing to SDK"
                )
                # PreToolUse hooks should still be there
                assert len(hook_config_passed.pre_tool_use) == 1, (
                    "Non-stop hooks should be preserved"
                )
