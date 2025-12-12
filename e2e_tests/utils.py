import os
from pathlib import Path
from typing import Any

from openhands.sdk import LLM
from openhands_cli.locations import AGENT_SETTINGS_PATH, PERSISTENCE_DIR
from openhands_cli.utils import (
    get_default_cli_agent,
    get_llm_metadata,
    should_set_litellm_extra_body,
)


def seed_dummy_settings():
    model_name = "dummy-model"
    extra_kwargs: dict[str, Any] = {}
    if should_set_litellm_extra_body(model_name):
        extra_kwargs["litellm_extra_body"] = {
            "metadata": get_llm_metadata(model_name=model_name, llm_type="openhands")
        }
    llm = LLM(model=model_name, api_key="dummy-key", **extra_kwargs)
    dummy_agent = get_default_cli_agent(llm=llm)

    spec_path = os.path.join(PERSISTENCE_DIR, AGENT_SETTINGS_PATH)
    specs_path = Path(os.path.expanduser(spec_path))

    if not specs_path.exists():
        specs_path.parent.mkdir(parents=True, exist_ok=True)
        specs_path.write_text(dummy_agent.model_dump_json())
