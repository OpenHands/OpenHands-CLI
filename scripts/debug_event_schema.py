import json

from pydantic import TypeAdapter

from openhands.sdk import MessageEvent
from openhands.sdk.event.base import Event


adapter = TypeAdapter(Event)
data = {
    "id": "1",  # ID usually string
    "timestamp": "2024-01-01T12:00:00Z",
    "source": "user",
    "kind": "MessageEvent",
    "llm_message": {
        "role": "user",
        "content": [{"type": "text", "text": "Test Event"}],
    },
}

print("Attempting validation...")
try:
    obj = adapter.validate_python(data)
    print("SUCCESS:", obj)
except Exception as e:
    print("ERROR:", e)

print("\nMessageEvent Schema (partial):")
schema = MessageEvent.model_json_schema()
print(json.dumps(schema.get("properties", {}).get("kind"), indent=2))
