# History panel plan (TUI)

> NOTE (NOT FOR COMMIT): This file is a working plan / design notes for the local
> repo only. Do **NOT** include `PLAN_HISTORY_COMMAND.md` into PR commits.

## Goal
Add `/history` command and a side panel to browse and resume **local** conversations.

## Scope decision
- **Local mode**: History panel is available; users can browse and resume local conversations
- **Cloud mode**: History panel is **disabled**; shows notification "History is not available in cloud mode"

Cloud conversation history was deprioritized because:
1. `prod-runtime.*` API is incompatible with SDK `RemoteConversation` (uses hex IDs + Socket.IO vs UUID + REST `/events/search`)
2. Implementing a custom runtime connector added complexity without reliable UX
3. Cloud users can use the web UI for conversation history

## Architecture

### Approach: Lazy Loading + Side Panel
- Reuse the `MCPSidePanel` pattern (side panel widget)
- Clicking a local conversation resumes it by loading from disk and replaying events into the TUI
- Note: we render user messages in history as normal chat lines (`> ...`) to match the live chat UX

### Why Side Panel (not Modal):
- Can see current conversation while selecting
- Consistent with MCP panel
- Faster to close (click or Esc)

## Status (implemented)
### ✅ Local
- Listed from persistence dir (`~/.openhands/conversations`)
- Resume: load and replay events via `ConversationVisualizer` + app-rendered user lines
- Full conversation id displayed
- Conversation title from first user message (up to 100 chars)
- Current/selected highlighting

### ❌ Cloud (out of scope)
- Cloud history is disabled in TUI
- Cloud users should use the web UI at `app.all-hands.dev`

## Files (implemented)
- `openhands_cli/tui/panels/history_side_panel.py`
- `openhands_cli/tui/panels/history_panel_style.py`
- `openhands_cli/tui/textual_app.py` (toggle, switch, cloud mode check)
- tests: snapshots

## UI Design

```
┌─────────────────────────────────────────────────────────────────┐
│ main_display                         │ Conversations            │
│                                      │ ─────────────────────────│
│                                      │ ▶ Fix the login bug...   │
│                                      │   abc123 • 2m ago        │
│                                      │                          │
│                                      │   Add dark mode...       │
│                                      │   def456 • 1h ago        │
│                                      │                          │
│                                      │   Refactor API...        │
│                                      │   ghi789 • yesterday     │
├─────────────────────────────────────────────────────────────────┤
│ > input                                                         │
└─────────────────────────────────────────────────────────────────┘
```

- `▶` (highlight) indicates current conversation
- Click on conversation → switch to it
- Ctrl+H → toggle panel

## Not in scope
- Cloud conversation history
- Deleting conversations
- Searching conversations
- Creating new cloud conversations from CLI
