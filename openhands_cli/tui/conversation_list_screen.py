"""Conversation list screen for OpenHands CLI."""

from uuid import UUID

from prompt_toolkit import HTML, print_formatted_text
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.shortcuts import button_dialog

from openhands_cli.conversation_history import (
    get_all_user_messages,
    get_total_conversation_count,
    list_conversations,
)
from openhands_cli.pt_style import get_cli_style


DEFAULT_STYLE = get_cli_style()
CONVERSATIONS_PER_PAGE = 10


class ConversationListScreen:
    """Screen for displaying and browsing conversation history."""

    def __init__(self):
        self.current_page = 0

    def display_conversations(self) -> UUID | None:
        """Display the conversation list with pagination.

        Returns:
            UUID of selected conversation to resume, or None if cancelled
        """
        while True:
            conversations = list_conversations(
                limit=CONVERSATIONS_PER_PAGE, offset=self.current_page * CONVERSATIONS_PER_PAGE
            )
            total_count = get_total_conversation_count()
            total_pages = (total_count + CONVERSATIONS_PER_PAGE - 1) // CONVERSATIONS_PER_PAGE

            if not conversations and self.current_page == 0:
                print_formatted_text("")
                print_formatted_text(
                    HTML("<yellow>No conversation history found.</yellow>")
                )
                print_formatted_text(
                    HTML(
                        "<grey>Conversations will appear here after you start chatting with the agent.</grey>"
                    )
                )
                print_formatted_text("")
                return None

            # Display header
            print_formatted_text("")
            print_formatted_text(HTML("<gold>🕒 Conversation History</gold>"))
            print_formatted_text(
                HTML(
                    f"<grey>Page {self.current_page + 1} of {max(1, total_pages)} "
                    f"({total_count} total conversations)</grey>"
                )
            )
            print_formatted_text("")

            # Display conversations
            for i, conv in enumerate(conversations, 1):
                offset_num = self.current_page * CONVERSATIONS_PER_PAGE + i
                print_formatted_text(
                    HTML(f"<white>{offset_num}.</white> {conv}")
                )

            print_formatted_text("")

            # Build button list
            buttons = []

            # Add navigation buttons
            if self.current_page > 0:
                buttons.append(("Previous Page", "prev"))

            if (self.current_page + 1) * CONVERSATIONS_PER_PAGE < total_count:
                buttons.append(("Next Page", "next"))

            # Add view/resume buttons for each conversation
            for i, conv in enumerate(conversations, 1):
                buttons.append((f"View #{self.current_page * CONVERSATIONS_PER_PAGE + i}", f"view_{i - 1}"))

            buttons.append(("Back", "back"))

            # Show dialog with buttons
            result = button_dialog(
                title="Conversation History",
                text=to_formatted_text(
                    HTML(
                        "Select an option:\n"
                        "• Use Previous/Next Page to navigate\n"
                        "• Use View #N to see all messages from a conversation\n"
                        "• Use Back to return to chat"
                    )
                ),
                buttons=buttons,
                style=DEFAULT_STYLE,
            ).run()

            if result == "back" or result is None:
                return None

            elif result == "prev":
                self.current_page = max(0, self.current_page - 1)

            elif result == "next":
                self.current_page += 1

            elif result.startswith("view_"):
                # Extract the index
                index = int(result.split("_")[1])
                if index < len(conversations):
                    selected_conv = conversations[index]
                    self._display_conversation_detail(selected_conv.id)

    def _display_conversation_detail(self, conversation_id: UUID) -> None:
        """Display all user messages from a conversation.

        Args:
            conversation_id: UUID of the conversation to display
        """
        messages = get_all_user_messages(conversation_id)

        if not messages:
            print_formatted_text("")
            print_formatted_text(
                HTML(
                    "<yellow>No user messages found in this conversation.</yellow>"
                )
            )
            print_formatted_text("")
            return

        # Display header
        print_formatted_text("")
        print_formatted_text(HTML(f"<gold>💬 Conversation: {conversation_id}</gold>"))
        print_formatted_text(
            HTML(f"<grey>Total user messages: {len(messages)}</grey>")
        )
        print_formatted_text("")

        # Display all messages
        for i, message in enumerate(messages, 1):
            print_formatted_text(HTML(f"<white>Message {i}:</white>"))
            print_formatted_text(f"  {message}")
            print_formatted_text("")

        # Show option to resume this conversation
        result = button_dialog(
            title=f"Conversation {conversation_id}",
            text=to_formatted_text(
                HTML(
                    f"Found {len(messages)} user message(s) in this conversation.\n"
                    "Would you like to resume this conversation?"
                )
            ),
            buttons=[
                ("Resume Conversation", "resume"),
                ("Back to List", "back"),
            ],
            style=DEFAULT_STYLE,
        ).run()

        if result == "resume":
            print_formatted_text("")
            print_formatted_text(
                HTML(
                    f"<grey>Hint:</grey> Run <gold>openhands --resume {conversation_id}</gold> "
                    "to resume this conversation."
                )
            )
            print_formatted_text("")
