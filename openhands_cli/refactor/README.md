# OpenHands CLI UI Refactor

This directory contains the new textual-based UI implementation for OpenHands CLI, migrating away from prompt_toolkit.

## Current Status

### ✅ Phase 1: Foundation Complete

- **Basic textual app structure** (`textual_app.py`)
- **Main container** using Static widget with borders
- **Input widget** at bottom with automatic focus
- **CSS-based responsive layout**
- **Basic event handling** for user input

## Files

### `textual_app.py`
The minimal textual application demonstrating the basic structure:
- `OpenHandsApp` class extending textual's `App`
- Main content area (Static widget) with border
- Input field at bottom with placeholder
- Automatic focus management
- Basic message display functionality

## Running the App

```bash
# Install textual (temporary - will be added to dependencies)
pip install textual

# Run the minimal app
python openhands_cli/refactor/textual_app.py
```

## Key Features Implemented

1. **Layout Structure**: Two-part vertical layout with main container and input
2. **Focus Management**: Input widget automatically focused on startup
3. **Responsive Design**: CSS-based layout using fractional units (1fr)
4. **Event Handling**: Input submission displays messages in main container
5. **Styling**: Border around main container, proper spacing

## Next Steps

See `UI_MIGRATION_CHECKLIST.md` in the project root for the complete migration plan and progress tracking.

### Phase 2: Core Interface (Next)
- Migrate main chat interface logic
- Implement command system (`/help`, `/exit`, etc.)
- Add input handling and keyboard shortcuts
- Implement basic display patterns

## Technical Notes

- Uses `Static` widget as main container (textual best practice)
- CSS styling with inline definitions
- Event-driven architecture with `on_input_submitted()`
- Automatic focus management through `on_mount()`