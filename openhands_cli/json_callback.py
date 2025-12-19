"""JSON event callback for headless mode with JSON output."""

import json
from rich.console import Console
from openhands.sdk.event import SystemPromptEvent
from openhands.sdk.event.base import Event

console = Console()


def json_callback(event: Event) -> None:
    if isinstance(event, SystemPromptEvent):
        return

    data = event.model_dump()
    pretty_json = json.dumps(data, indent=2, sort_keys=True)
    print("--JSON Event--")
    print(pretty_json)