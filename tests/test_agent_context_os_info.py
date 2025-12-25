from unittest.mock import MagicMock, patch

from openhands.sdk import LLM, Agent
from openhands_cli.stores import AgentStore


def test_agent_context_includes_os_info() -> None:
    mock_agent = Agent(
        llm=LLM(model="test/model", api_key="test-key", usage_id="test-service"),
    )

    with (
        patch("openhands_cli.stores.agent_store.LocalFileStore") as mock_file_store,
        patch(
            "openhands_cli.stores.agent_store.get_os_description",
            return_value="TestOS 1.0",
        ),
        patch("openhands_cli.stores.agent_store.list_enabled_servers", return_value=[]),
    ):
        mock_store_instance = MagicMock()
        mock_file_store.return_value = mock_store_instance
        mock_store_instance.read.return_value = mock_agent.model_dump_json()

        loaded_agent = AgentStore().load()
        assert loaded_agent is not None
        assert loaded_agent.agent_context is not None

        suffix = loaded_agent.agent_context.system_message_suffix or ""
        assert "User operating system: TestOS" in suffix
