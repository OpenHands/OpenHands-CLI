"""ScrollableContent widget for conversation content display.

This module provides ScrollableContent, a simple VerticalScroll container that
holds conversation content (splash screen and dynamically added messages).

Widget Hierarchy (within ConversationView):
    ConversationView(Container, #conversation_view)
    ├── ScrollableContent(VerticalScroll, #scroll_view)
    │   ├── SplashContent(#splash_content)
    │   └── ... dynamically added conversation widgets
    └── InputAreaContainer(#input_area)  ← docked to bottom
        ├── WorkingStatusLine
        ├── InputField
        └── InfoStatusLine

Message handling (UserInputSubmitted, SlashCommandSubmitted) is done by
ConversationView, not by ScrollableContent.
"""

from textual.containers import VerticalScroll


class ScrollableContent(VerticalScroll):
    """Scrollable container for conversation content.

    This widget holds:
    - SplashContent at the top
    - Dynamically added conversation widgets (user messages, agent responses)

    It's a simple container - all message handling is done by ConversationView.
    """

    pass
