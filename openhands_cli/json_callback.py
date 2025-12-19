"""JSON event callback for headless mode with JSON output."""

import json
import sys
from typing import Any, Dict

from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
    PauseEvent,
    SystemPromptEvent,
    UserRejectObservation,
)
from openhands.sdk.event.base import Event
from openhands.sdk.event.condenser import Condensation, CondensationRequest
from openhands.sdk.event.conversation_error import ConversationErrorEvent


def create_json_event_callback():
    """Create a callback function that prints events as JSONL to terminal.
    
    Returns:
        A callback function that takes an event and prints it as JSON to stdout.
    """
    
    def json_event_callback(event: Event) -> None:
        """Print event as JSONL to terminal.
        
        Args:
            event: The event to serialize and print
        """
        try:
            # Create a basic event dictionary
            event_data: Dict[str, Any] = {
                "event_type": event.__class__.__name__,
                "timestamp": getattr(event, "timestamp", None),
            }
            
            # Add event-specific data based on event type
            if isinstance(event, ActionEvent):
                event_data.update({
                    "action_type": event.action.__class__.__name__ if event.action else None,
                    "action_data": _serialize_action(event.action) if event.action else None,
                })
            
            elif isinstance(event, ObservationEvent):
                event_data.update({
                    "observation_type": event.observation.__class__.__name__ if event.observation else None,
                    "observation_data": _serialize_observation(event.observation) if event.observation else None,
                })
            
            elif isinstance(event, MessageEvent):
                event_data.update({
                    "message": _serialize_message(event.llm_message) if event.llm_message else None,
                })
            
            elif isinstance(event, AgentErrorEvent):
                event_data.update({
                    "error": str(event.error) if hasattr(event, "error") else None,
                })
            
            elif isinstance(event, ConversationErrorEvent):
                event_data.update({
                    "error": str(event.error) if hasattr(event, "error") else None,
                })
            
            elif isinstance(event, PauseEvent):
                event_data.update({
                    "reason": getattr(event, "reason", None),
                })
            
            elif isinstance(event, UserRejectObservation):
                event_data.update({
                    "rejection_reason": getattr(event, "reason", None),
                })
            
            elif isinstance(event, SystemPromptEvent):
                event_data.update({
                    "prompt": getattr(event, "prompt", None),
                })
            
            elif isinstance(event, (Condensation, CondensationRequest)):
                event_data.update({
                    "condensation_data": _serialize_condensation(event),
                })
            
            # Add any additional attributes that might be useful
            for attr in ["id", "source", "extra"]:
                if hasattr(event, attr):
                    value = getattr(event, attr)
                    if value is not None:
                        event_data[attr] = value
            
            # Print as JSONL (one JSON object per line)
            print(json.dumps(event_data, default=str), flush=True)
            
        except Exception as e:
            # If serialization fails, print a basic error event
            error_data = {
                "event_type": "SerializationError",
                "original_event_type": event.__class__.__name__,
                "error": str(e),
                "timestamp": getattr(event, "timestamp", None),
            }
            print(json.dumps(error_data, default=str), flush=True)
    
    return json_event_callback


def _serialize_action(action) -> Dict[str, Any]:
    """Serialize an action object to a dictionary.
    
    Args:
        action: The action object to serialize
        
    Returns:
        Dictionary representation of the action
    """
    if not action:
        return {}
    
    action_data = {"type": action.__class__.__name__}
    
    # Common action attributes
    for attr in ["command", "path", "content", "message", "text", "query", "args"]:
        if hasattr(action, attr):
            value = getattr(action, attr)
            if value is not None:
                action_data[attr] = value
    
    return action_data


def _serialize_observation(observation) -> Dict[str, Any]:
    """Serialize an observation object to a dictionary.
    
    Args:
        observation: The observation object to serialize
        
    Returns:
        Dictionary representation of the observation
    """
    if not observation:
        return {}
    
    obs_data = {"type": observation.__class__.__name__}
    
    # Common observation attributes
    for attr in ["content", "exit_code", "error", "stdout", "stderr", "path"]:
        if hasattr(observation, attr):
            value = getattr(observation, attr)
            if value is not None:
                obs_data[attr] = value
    
    return obs_data


def _serialize_message(message) -> Dict[str, Any]:
    """Serialize a message object to a dictionary.
    
    Args:
        message: The message object to serialize
        
    Returns:
        Dictionary representation of the message
    """
    if not message:
        return {}
    
    message_data = {
        "role": getattr(message, "role", None),
    }
    
    # Handle content which can be a list or string
    if hasattr(message, "content"):
        content = message.content
        if isinstance(content, list):
            # Extract text from content list
            content_text = ""
            for item in content:
                if hasattr(item, "text"):
                    content_text += item.text
                elif hasattr(item, "content"):
                    content_text += str(item.content)
                else:
                    content_text += str(item)
            message_data["content"] = content_text
        else:
            message_data["content"] = str(content) if content is not None else None
    
    return message_data


def _serialize_condensation(event) -> Dict[str, Any]:
    """Serialize a condensation event to a dictionary.
    
    Args:
        event: The condensation event to serialize
        
    Returns:
        Dictionary representation of the condensation
    """
    condensation_data = {}
    
    # Add any relevant condensation attributes
    for attr in ["summary", "events_condensed", "reason"]:
        if hasattr(event, attr):
            value = getattr(event, attr)
            if value is not None:
                condensation_data[attr] = value
    
    return condensation_data