#!/usr/bin/env python3

from unittest.mock import MagicMock, call, patch

import pytest

from openhands_cli.runner import ConversationRunner


CONV_ID = "test-conversation-id"


# ---------- Helpers ----------
def make_conv(enabled: bool) -> MagicMock:
    """Return a conversation mock in enabled/disabled confirmation mode."""
    m = MagicMock()
    m.id = CONV_ID
    m.agent.security_analyzer = MagicMock() if enabled else None
    m.confirmation_policy_active = enabled
    m.is_confirmation_mode_active = enabled
    return m


@pytest.fixture
def runner_disabled() -> ConversationRunner:
    """Runner starting with confirmation mode disabled."""
    return ConversationRunner(make_conv(enabled=False))


@pytest.fixture
def runner_enabled() -> ConversationRunner:
    """Runner starting with confirmation mode enabled."""
    return ConversationRunner(make_conv(enabled=True))


# ---------- Core toggle behavior (parametrized) ----------
@pytest.mark.parametrize(
    "start_enabled, confirmation_mode, expected_enabled",
    [
        # disabled -> enable (use always-ask mode)
        (False, "always-ask", True),
        # enabled -> disable (use always-approve mode)
        (True, "always-approve", False),
    ],
)
def test_toggle_confirmation_mode_transitions(
    start_enabled, confirmation_mode, expected_enabled
):
    # Arrange: pick starting runner & prepare the target conversation
    runner = ConversationRunner(make_conv(enabled=start_enabled))
    target_conv = make_conv(enabled=expected_enabled)

    with patch(
        "openhands_cli.runner.setup_conversation", return_value=target_conv
    ) as mock_setup:
        # Act
        runner.toggle_confirmation_mode()

        # Assert state
        assert runner.is_confirmation_mode_active is expected_enabled
        assert runner.conversation is target_conv

        # Assert setup called with same conversation ID + correct confirmation mode
        mock_setup.assert_called_once_with(CONV_ID, confirmation_mode=confirmation_mode)

        # Policy is set inside setup_conversation, not called explicitly in toggle
        target_conv.set_confirmation_policy.assert_not_called()


# ---------- Conversation ID is preserved across multiple toggles ----------
def test_maintains_conversation_id_across_toggles(runner_disabled: ConversationRunner):
    enabled_conv = make_conv(enabled=True)
    disabled_conv = make_conv(enabled=False)

    with patch("openhands_cli.runner.setup_conversation") as mock_setup:
        mock_setup.side_effect = [enabled_conv, disabled_conv]

        # Toggle on (disabled -> enabled uses always-ask),
        # then off (enabled -> disabled uses always-approve)
        runner_disabled.toggle_confirmation_mode()
        runner_disabled.toggle_confirmation_mode()

        assert runner_disabled.conversation.id == CONV_ID
        mock_setup.assert_has_calls(
            [
                call(CONV_ID, confirmation_mode="always-ask"),
                call(CONV_ID, confirmation_mode="always-approve"),
            ],
            any_order=False,
        )


# ---------- Idempotency under rapid alternating toggles ----------
def test_rapid_alternating_toggles_produce_expected_states(
    runner_disabled: ConversationRunner,
):
    enabled_conv = make_conv(enabled=True)
    disabled_conv = make_conv(enabled=False)

    with patch("openhands_cli.runner.setup_conversation") as mock_setup:
        mock_setup.side_effect = [
            enabled_conv,
            disabled_conv,
            enabled_conv,
            disabled_conv,
        ]

        # Start disabled
        assert runner_disabled.is_confirmation_mode_active is False

        # Enable (always-ask), Disable (always-approve),
        # Enable (always-ask), Disable (always-approve)
        runner_disabled.toggle_confirmation_mode()
        assert runner_disabled.is_confirmation_mode_active is True

        runner_disabled.toggle_confirmation_mode()
        assert runner_disabled.is_confirmation_mode_active is False

        runner_disabled.toggle_confirmation_mode()
        assert runner_disabled.is_confirmation_mode_active is True

        runner_disabled.toggle_confirmation_mode()
        assert runner_disabled.is_confirmation_mode_active is False

        mock_setup.assert_has_calls(
            [
                call(CONV_ID, confirmation_mode="always-ask"),
                call(CONV_ID, confirmation_mode="always-approve"),
                call(CONV_ID, confirmation_mode="always-ask"),
                call(CONV_ID, confirmation_mode="always-approve"),
            ],
            any_order=False,
        )
