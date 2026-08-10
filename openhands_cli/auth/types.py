"""Type definitions for authentication and user settings."""

from typing import Any, TypedDict


class AgentLLMSettings(TypedDict, total=False):
    """LLM configuration nested in agent_settings."""

    model: str
    base_url: str | None


class AgentSettings(TypedDict, total=False):
    """Agent configuration nested in user settings."""

    agent: str
    llm: AgentLLMSettings


class UserSettings(TypedDict, total=False):
    """User settings from the OpenHands API.

    This represents the flattened settings structure used throughout the CLI,
    where nested agent_settings fields are surfaced at the top level for
    backward compatibility.
    """

    llm_model: str
    llm_base_url: str | None
    agent: str
    language: str
    llm_api_key_set: bool
    agent_settings: AgentSettings


class UserData(TypedDict):
    """User data returned from fetch_user_data_after_oauth."""

    llm_api_key: str | None
    settings: UserSettings | dict[str, Any] | None
