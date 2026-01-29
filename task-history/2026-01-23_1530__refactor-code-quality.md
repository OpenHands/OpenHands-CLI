# Task 2026-01-23_1530__refactor-code-quality: Code Quality Improvements

## Meta
- Status: completed
- Parent task: none
- Chat links:
  - Cursor: current session
- Areas: backend
- Repos:
  - /Users/pavel.shvetsov/PycharmProjects/OpenHands-CLI
- Created at: 2026-01-23 15:30
- Updated at: 2026-01-23 16:30

## Todos
- [x] 1. Reuse: Extract `_hide_all_panes()` method (duplicated in switch_active_pane and create_new)
- [x] 2. Reuse: Use `format_conversation_header()` from splash.py for header formatting
- [x] 3. DIP: Access session_manager through public API, not `app._session_manager`
- [x] 4. Type safety: Fix return type of `get_active_content_container` to `VerticalScroll | Container`
- [x] 5. Constants: Create constants for CSS classes in ConversationPane
- [x] 6. Errors: Add logging for error handling (following plan_side_panel.py pattern)
- [x] 7. Run all tests (unit + e2e) - 1149 tests passed
- [x] 8. Update task card with results

## Cognitive State

### Goal
- Improve code quality: reduce duplication, fix type hints, add proper error logging

### Context
- ConversationPane, ConversationSwitcher, ConversationManager, textual_app.py were modified
- Need to follow existing patterns in the codebase
- Textual message passing is preferred for UI communication
- Error handling should use logging (like plan_side_panel.py)

### History
- [T0] Reviewed code for SOLID, style, best practices, reuse issues
- [T1] Identified 7 improvements to implement

### Hypotheses
- H1: Extracting `_hide_all_panes()` will reduce duplication
- H2: Using `get_conversation_text()` ensures consistent styling

### Decisions / Contracts
- Skip SOLID refactoring of ConversationPane (per user request)
- Keep Textual message passing pattern
- Use logging for debug-level error info (not notify for non-critical)

### Product Requirements files read and changes
- N/A (code quality task)

### Open Questions
- None

## Commits
- (pending user review)

## Guides Changes
- None

## Notes
- Following existing patterns from plan_side_panel.py for logging
- CSS class constants follow Python naming conventions
- Fixed bug in delegation user message rendering (was returning None)
- Updated test `test_new_command_clears_dynamically_added_widgets` → `test_new_command_hides_conversation_panes` to reflect new behavior
- Updated 13 snapshot tests
- All 1149 unit tests + 3 e2e tests pass

## Files Modified
- `openhands_cli/tui/textual_app.py` - added `_hide_all_panes()`, `session_manager` property, fixed return type
- `openhands_cli/tui/core/conversation_manager.py` - use `_hide_all_panes()`, `session_manager` 
- `openhands_cli/tui/core/conversation_switcher.py` - use `session_manager`
- `openhands_cli/tui/panels/conversation_pane.py` - CSS constants, logging
- `openhands_cli/tui/content/splash.py` - added `format_conversation_header()`
- `openhands_cli/tui/widgets/richlog_visualizer.py` - fixed type hint, hasattr for scroll_end, fixed delegation rendering
- `tests/tui/test_commands.py` - updated test for new /new behavior
- `tests/tui/test_textual_app.py` - fixed test for _finish_switch signature
- `tests/snapshots/` - 13 snapshots updated
