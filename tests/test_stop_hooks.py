"""Tests for CLI-level stop hook handling."""

from openhands.sdk.hooks import (
    HookConfig,
    HookDefinition,
    HookMatcher,
)
from openhands_cli.setup import strip_stop_hooks
from openhands_cli.stop_hooks import run_stop_hooks


class TestStripStopHooks:
    """Tests for strip_stop_hooks()."""

    def test_no_stop_hooks_returns_unchanged(self):
        config = HookConfig(
            pre_tool_use=[
                HookMatcher(matcher="*", hooks=[HookDefinition(command="echo pre")])
            ]
        )
        result_config, stop_matchers = strip_stop_hooks(config)
        assert stop_matchers == []
        assert result_config.pre_tool_use == config.pre_tool_use
        assert result_config.stop == []

    def test_stop_hooks_are_stripped(self):
        stop_matcher = HookMatcher(
            matcher="*", hooks=[HookDefinition(command="echo stop")]
        )
        config = HookConfig(
            pre_tool_use=[
                HookMatcher(matcher="*", hooks=[HookDefinition(command="echo pre")])
            ],
            stop=[stop_matcher],
        )
        result_config, stop_matchers = strip_stop_hooks(config)
        assert len(stop_matchers) == 1
        assert stop_matchers[0].matcher == "*"
        assert result_config.stop == []
        # Other hooks are preserved
        assert len(result_config.pre_tool_use) == 1

    def test_empty_config(self):
        config = HookConfig()
        result_config, stop_matchers = strip_stop_hooks(config)
        assert stop_matchers == []
        assert result_config.is_empty()

    def test_only_stop_hooks(self):
        config = HookConfig(
            stop=[HookMatcher(matcher="*", hooks=[HookDefinition(command="echo stop")])]
        )
        result_config, stop_matchers = strip_stop_hooks(config)
        assert len(stop_matchers) == 1
        assert result_config.is_empty()

    def test_multiple_stop_matchers(self):
        config = HookConfig(
            stop=[
                HookMatcher(
                    matcher="pattern1",
                    hooks=[HookDefinition(command="echo one")],
                ),
                HookMatcher(
                    matcher="pattern2",
                    hooks=[HookDefinition(command="echo two")],
                ),
            ]
        )
        result_config, stop_matchers = strip_stop_hooks(config)
        assert len(stop_matchers) == 2
        assert result_config.stop == []


class TestRunStopHooks:
    """Tests for run_stop_hooks()."""

    def test_no_matchers_allows_stop(self):
        should_stop, feedback = run_stop_hooks(
            stop_matchers=[],
            session_id="test-session",
            working_dir="/tmp",
        )
        assert should_stop is True
        assert feedback is None

    def test_successful_hook_allows_stop(self):
        """A hook that exits 0 allows the agent to stop."""
        matchers = [
            HookMatcher(
                matcher="*",
                hooks=[HookDefinition(command="exit 0")],
            )
        ]
        should_stop, feedback = run_stop_hooks(
            stop_matchers=matchers,
            session_id="test-session",
            working_dir="/tmp",
        )
        assert should_stop is True
        assert feedback is None

    def test_hook_exit_code_2_blocks_stop(self):
        """A hook that deliberately exits 2 (block protocol) denies the stop."""
        matchers = [
            HookMatcher(
                matcher="*",
                hooks=[HookDefinition(command="exit 2")],
            )
        ]
        should_stop, feedback = run_stop_hooks(
            stop_matchers=matchers,
            session_id="test-session",
            working_dir="/tmp",
        )
        assert should_stop is False
        assert feedback is not None

    def test_missing_python_script_allows_stop(self):
        """Exit code 2 from a missing Python script should allow stop (not block)."""
        matchers = [
            HookMatcher(
                matcher="*",
                hooks=[
                    HookDefinition(command="python3 /nonexistent_stop_hook_script.py")
                ],
            )
        ]
        should_stop, feedback = run_stop_hooks(
            stop_matchers=matchers,
            session_id="test-session",
            working_dir="/tmp",
        )
        assert should_stop is True
        assert feedback is None

    def test_hook_timeout_allows_stop(self):
        """A hook that times out should allow stop."""
        matchers = [
            HookMatcher(
                matcher="*",
                hooks=[HookDefinition(command="sleep 60", timeout=1)],
            )
        ]
        should_stop, feedback = run_stop_hooks(
            stop_matchers=matchers,
            session_id="test-session",
            working_dir="/tmp",
        )
        assert should_stop is True
        assert feedback is None

    def test_hook_crash_allows_stop(self):
        """A hook that crashes (non-zero, non-2) should allow stop."""
        matchers = [
            HookMatcher(
                matcher="*",
                hooks=[HookDefinition(command="exit 1")],
            )
        ]
        should_stop, feedback = run_stop_hooks(
            stop_matchers=matchers,
            session_id="test-session",
            working_dir="/tmp",
        )
        assert should_stop is True
        assert feedback is None

    def test_hook_json_deny_blocks_stop(self):
        """A hook that outputs JSON {\"decision\": \"deny\"} should block."""
        matchers = [
            HookMatcher(
                matcher="*",
                hooks=[
                    HookDefinition(
                        command='echo \'{"decision": "deny", "reason": "not yet"}\''
                    )
                ],
            )
        ]
        should_stop, feedback = run_stop_hooks(
            stop_matchers=matchers,
            session_id="test-session",
            working_dir="/tmp",
        )
        assert should_stop is False
        assert feedback is not None
        assert "not yet" in feedback

    def test_hook_json_allow_permits_stop(self):
        """A hook that outputs JSON {\"decision\": \"allow\"} should allow stop."""
        matchers = [
            HookMatcher(
                matcher="*",
                hooks=[HookDefinition(command='echo \'{"decision": "allow"}\'')],
            )
        ]
        should_stop, feedback = run_stop_hooks(
            stop_matchers=matchers,
            session_id="test-session",
            working_dir="/tmp",
        )
        assert should_stop is True
        assert feedback is None

    def test_exit_code_2_with_file_not_found_stderr_allows_stop(self):
        """Exit code 2 with stderr indicating file-not-found should allow stop.

        This is the key scenario from issue #649: Python exits with code 2
        when it can't find a script file, and the SDK treats that as 'block'.
        """
        # Create a script that mimics Python's "can't open file" behavior
        matchers = [
            HookMatcher(
                matcher="*",
                hooks=[
                    HookDefinition(
                        command=(
                            "echo \"can't open file '/nonexistent.py': "
                            '[Errno 2] No such file or directory" >&2; exit 2'
                        )
                    )
                ],
            )
        ]
        should_stop, feedback = run_stop_hooks(
            stop_matchers=matchers,
            session_id="test-session",
            working_dir="/tmp",
        )
        assert should_stop is True
        assert feedback is None

    def test_multiple_hooks_first_blocks(self):
        """When first hook blocks, second hook should not run."""
        matchers = [
            HookMatcher(
                matcher="*",
                hooks=[
                    HookDefinition(command="exit 2"),
                    HookDefinition(command="exit 0"),
                ],
            )
        ]
        should_stop, feedback = run_stop_hooks(
            stop_matchers=matchers,
            session_id="test-session",
            working_dir="/tmp",
        )
        assert should_stop is False

    def test_real_python_missing_script_exit_code(self):
        """Verify that Python actually exits with code 2 for missing scripts,
        and our handler correctly allows the stop."""
        matchers = [
            HookMatcher(
                matcher="*",
                hooks=[
                    HookDefinition(
                        command="python3 /tmp/this_script_does_not_exist_12345.py"
                    )
                ],
            )
        ]
        should_stop, feedback = run_stop_hooks(
            stop_matchers=matchers,
            session_id="test-session",
            working_dir="/tmp",
        )
        assert should_stop is True
        assert feedback is None
