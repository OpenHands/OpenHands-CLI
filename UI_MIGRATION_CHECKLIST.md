# OpenHands CLI UI Migration Checklist

## Overview
This document tracks the migration from prompt_toolkit to textual library for the OpenHands CLI user interface. The migration will be done incrementally to ensure stability and maintainability.

## Current UI Architecture (prompt_toolkit)

### Main Components

#### 1. **Main Chat Interface** (`agent_chat.py`)
- [x] **Analyzed** - Main conversation loop with user input handling
- [ ] **Migrated** - Core chat interface
- **Features:**
  - Interactive prompt with `> ` prefix
  - Command completion with `/` commands
  - Multiline input support (\ + Enter for newlines)
  - Keyboard shortcuts (Ctrl+C for interrupt)
  - Session management and conversation state

#### 2. **Welcome/Banner Display** (`tui/tui.py`)
- [x] **Analyzed** - Welcome screen and banner display
- [ ] **Migrated** - Welcome screen
- **Features:**
  - ASCII art OpenHands logo
  - Conversation ID display
  - Version information and update notifications
  - Welcome message and help hints

#### 3. **Command System** (`tui/tui.py`)
- [x] **Analyzed** - Command completion and help system
- [ ] **Migrated** - Command system
- **Features:**
  - Command completer with dropdown suggestions
  - Available commands: `/exit`, `/help`, `/clear`, `/new`, `/status`, `/confirm`, `/resume`, `/settings`, `/mcp`
  - Command descriptions and help text
  - Interactive command selection

#### 4. **Settings Screen** (`tui/settings/settings_screen.py`)
- [x] **Analyzed** - Settings configuration interface
- [ ] **Migrated** - Settings screen
- **Features:**
  - Settings display in framed container
  - Basic vs Advanced settings modes
  - LLM provider/model selection
  - API key management (masked display)
  - Memory condensation toggle
  - Configuration file path display
  - Step-by-step configuration wizard

#### 5. **Status Display** (`tui/status.py`)
- [x] **Analyzed** - Conversation status and metrics
- [ ] **Migrated** - Status display
- **Features:**
  - Conversation ID and uptime display
  - Token usage metrics (input/output/cache)
  - Cost tracking
  - Formatted containers with frames
  - Aligned column display

#### 6. **MCP Screen** (`tui/settings/mcp_screen.py`)
- [x] **Analyzed** - MCP server configuration display
- [ ] **Migrated** - MCP screen
- **Features:**
  - MCP server information display
  - Configuration details

#### 7. **User Input Components** (`user_actions/utils.py`)
- [x] **Analyzed** - Various input widgets and confirmations
- [ ] **Migrated** - Input components
- **Features:**
  - Confirmation dialogs with arrow key navigation
  - Text input prompts with validation
  - Password input (masked)
  - Keyboard shortcuts and escape handling
  - Custom validators

### UI Patterns and Behaviors

#### Input Handling
- [x] **Analyzed** - Input patterns and keyboard shortcuts
- [ ] **Migrated** - Input handling
- **Patterns:**
  - Main prompt session with command completion
  - Multi-choice selection with arrow keys
  - Text input with validation
  - Escape sequences (Ctrl+C, Ctrl+P, Escape)
  - Enter key handling for different contexts

#### Display Patterns
- [x] **Analyzed** - Display and formatting patterns
- [ ] **Migrated** - Display patterns
- **Patterns:**
  - HTML-formatted text with colors (gold, grey, red, green, yellow)
  - Framed containers for structured data
  - Aligned column layouts
  - Clear screen functionality
  - Spacing and formatting consistency

#### State Management
- [x] **Analyzed** - Application state and flow
- [ ] **Migrated** - State management
- **Patterns:**
  - Conversation state tracking
  - Session persistence
  - Settings persistence
  - Command routing and handling
  - Error handling and recovery

## Migration Strategy

### Phase 1: Foundation (Current)
- [x] **Analyze existing UI structure**
- [x] **Create refactor directory structure**
- [x] **Build minimal textual app with Container and Input**
- [x] **Establish basic layout and focus management**

### Phase 2: Core Interface
- [ ] **Migrate main chat interface**
- [ ] **Implement command system**
- [ ] **Add input handling and keyboard shortcuts**
- [ ] **Implement basic display patterns**

### Phase 3: Screens and Dialogs
- [ ] **Migrate welcome/banner screen**
- [ ] **Migrate settings screen**
- [ ] **Migrate status display**
- [ ] **Migrate MCP screen**

### Phase 4: Advanced Features
- [ ] **Migrate confirmation dialogs**
- [ ] **Implement validation system**
- [ ] **Add advanced input components**
- [ ] **Polish and optimize**

### Phase 5: Integration and Testing
- [ ] **Integration testing**
- [ ] **Performance optimization**
- [ ] **Documentation updates**
- [ ] **Remove prompt_toolkit dependencies**

## Technical Notes

### Key Dependencies to Replace
- `prompt_toolkit` → `textual`
- `prompt_toolkit.shortcuts` → textual equivalents
- `prompt_toolkit.formatted_text.HTML` → textual markup
- `prompt_toolkit.widgets` → textual widgets
- `prompt_toolkit.layout` → textual layout system

### Textual Components Needed
- `App` - Main application
- `Container` - Layout container
- `Input` - Text input widget
- `Static` - Text display
- `Vertical`/`Horizontal` - Layout containers
- `Screen` - Different app screens
- Custom widgets for specific functionality

### Styling Migration
- HTML-style color tags → textual CSS/styling
- prompt_toolkit styles → textual themes
- Frame widgets → textual containers with borders

## Progress Tracking

**Overall Progress: 40% (Foundation Complete)**

- ✅ **Analysis Phase**: Complete
- ✅ **Foundation Phase**: Complete
- ⏳ **Core Interface Phase**: Pending
- ⏳ **Screens Phase**: Pending
- ⏳ **Advanced Features Phase**: Pending
- ⏳ **Integration Phase**: Pending

## Implementation Notes

### Phase 1 Completed Items

#### Textual App Structure (`openhands_cli/refactor/textual_app.py`)
- ✅ **Basic App Class**: Created `OpenHandsApp` extending textual's `App`
- ✅ **Main Container**: Implemented using `Static` widget with border and padding
- ✅ **Input Widget**: Added at bottom with placeholder text and proper focus
- ✅ **Layout System**: Used CSS for responsive layout (1fr for main container, fixed height for input)
- ✅ **Focus Management**: Input widget automatically receives focus on app start
- ✅ **Basic Interaction**: Input submission handler displays messages in main container

#### Key Technical Decisions
- **Container Widget**: Used `Static` widget instead of a generic Container (textual pattern)
- **Layout**: CSS-based layout with fractional units (1fr) for responsive design
- **Focus**: Automatic focus management through `on_mount()` method
- **Styling**: Inline CSS for component styling and borders
- **Event Handling**: `on_input_submitted()` for processing user input

#### Dependencies Added
- **textual**: Core UI framework (temporarily installed for testing)
- **rich**: Dependency of textual for rendering (auto-installed)

---

*This checklist will be updated as migration progresses. Each component will be marked as analyzed, in progress, or completed.*