#!/usr/bin/env python3
"""Example script demonstrating how to use ConversationLister."""

from openhands_cli.conversations.lister import ConversationLister


def main():
    """Example usage of ConversationLister."""
    # Create a lister instance (uses CONVERSATIONS_DIR from locations)
    lister = ConversationLister()

    # List all conversations
    conversations = lister.list()

    if not conversations:
        print("No conversations found.")
        return

    print(f"Found {len(conversations)} conversation(s):")
    print("-" * 80)

    for i, conv in enumerate(conversations, 1):
        print(f"{i}. Conversation ID: {conv.id}")
        print(f"   Created: {conv.created_date.strftime('%Y-%m-%d %H:%M:%S')}")

        if conv.first_user_prompt:
            # Truncate long prompts for display
            prompt = conv.first_user_prompt
            if len(prompt) > 100:
                prompt = prompt[:97] + "..."
            print(f"   First prompt: {prompt}")
        else:
            print("   First prompt: (No user message found)")

        print()


if __name__ == "__main__":
    main()
