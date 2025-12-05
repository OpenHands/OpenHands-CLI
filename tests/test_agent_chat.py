from types import SimpleNamespace

from openhands.sdk.conversation.state import ConversationExecutionStatus
from openhands_cli import agent_chat


def _capture_messages(monkeypatch):
    messages: list[str] = []

    def _collector(value):
        messages.append(str(value))

    monkeypatch.setattr(agent_chat, "print_formatted_text", _collector)
    return messages


def test_run_cli_entry_headless_requires_input(monkeypatch):
    messages = _capture_messages(monkeypatch)
    monkeypatch.setattr(agent_chat, "verify_agent_exists_or_setup_agent", lambda: object())
    monkeypatch.setattr(agent_chat, "display_welcome", lambda *args, **kwargs: None)

    agent_chat.run_cli_entry(headless=True, queued_inputs=None)

    assert any("Headless mode requires" in message for message in messages)


def test_run_cli_entry_headless_exits_on_finish(monkeypatch):
    messages = _capture_messages(monkeypatch)
    monkeypatch.setattr(agent_chat, "verify_agent_exists_or_setup_agent", lambda: object())
    monkeypatch.setattr(agent_chat, "display_welcome", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_chat, "_restore_tty", lambda: None)

    conversation_state = SimpleNamespace(
        execution_status=ConversationExecutionStatus.RUNNING
    )
    conversation = SimpleNamespace(state=conversation_state)

    created_runners: list[SimpleNamespace] = []

    class FakeRunner:
        def __init__(self, conv):
            self.conversation = conv
            self.is_confirmation_mode_active = False
            self.last_message = None
            created_runners.append(self)

        def toggle_confirmation_mode(self):
            self.is_confirmation_mode_active = not self.is_confirmation_mode_active

        def process_message(self, message):
            self.last_message = message
            self.conversation.state.execution_status = (
                ConversationExecutionStatus.FINISHED
            )

    monkeypatch.setattr(agent_chat, "setup_conversation", lambda *args, **kwargs: conversation)
    monkeypatch.setattr(agent_chat, "ConversationRunner", FakeRunner)

    agent_chat.run_cli_entry(queued_inputs=["list files"], headless=True)

    assert created_runners, "ConversationRunner should be instantiated"
    runner = created_runners[0]
    assert runner.last_message is not None
    assert any("Agent finished execution" in message for message in messages)
