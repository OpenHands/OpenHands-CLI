# Code Quality Analysis Report

**Repository:** OpenHands CLI  
**Date:** 2026-07-06  
**Pyright Version:** 1.1.407  
**Files Analyzed:** 248  

---

## Executive Summary

The OpenHands CLI codebase demonstrates **good overall code quality** with solid architecture patterns, particularly in the TUI's reactive state management. Pyright reports **zero type errors** across all 248 analyzed files. However, there are opportunities for improvement in:

1. **Type Annotations:** ~80+ functions missing return types; ~25 uses of `Any` that could be more specific
2. **Code Duplication:** Significant duplication (~150-200 lines) between ACP and TUI implementations
3. **Separation of Concerns:** Some large files (836 lines for `richlog_visualizer.py`) mixing rendering logic with business logic
4. **State Management:** Generally well-implemented with reactive patterns; no critical issues found

The most impactful improvements would be extracting shared logic from ACP/TUI into the `shared/` module and adding type hints to public APIs.

---

## Type Checking Issues

### ✅ Critical Issues: Type Errors

**Pyright reports 0 errors, 0 warnings across all files.** No critical type errors that could cause runtime bugs.

### Missing Type Hints

Approximately **80+ functions** are missing return type annotations. Key areas:

| Module | Functions Missing Return Types | Examples |
|--------|-------------------------------|----------|
| `acp_impl/agent/base_agent.py` | 15+ | `__init__`, `initialize`, `prompt`, `authenticate` |
| `acp_impl/agent/local_agent.py` | 4 | `__init__`, `_get_or_create_conversation`, `_setup_conversation` |
| `acp_impl/agent/remote_agent.py` | 6 | `__init__`, `_setup_conversation`, `new_session` |
| `acp_impl/events/shared_event_handler.py` | 5 | Event handler methods |
| `acp_impl/slash_commands.py` | 3 | `apply_confirmation_mode_to_conversation`, `get_confirmation_mode_from_conversation` |
| `tui/widgets/richlog_visualizer.py` | 9+ | `_run_on_main_thread`, `_extract_meaningful_title`, rendering methods |
| `tui/core/state.py` | 2 | `__init__`, `attach_conversation_state` |
| `tui/core/conversation_runner.py` | 3 | `__init__`, `process_message_async` |
| `auth/api_client.py` | 5 | `create_conversation`, `_ask_user_consent_for_overwrite` |
| `stores/agent_store.py` | 5 | `load_or_create`, `_with_llm_metadata`, `create_and_save_from_settings` |

### Type Improvement Opportunities

#### High-Priority `Any` Replacements

| File | Line | Current | Suggested |
|------|------|---------|-----------|
| `acp_impl/agent/base_agent.py` | 227-228 | `client_capabilities: Any \| None` | Protocol type from `acp` library |
| `acp_impl/agent/base_agent.py` | 355, 365 | `mcp_servers: list[Any] \| None` | `list[McpServerSpec]` |
| `acp_impl/events/token_streamer.py` | 242 | `tool_call: Any` | `ToolCallDelta` |
| `auth/api_client.py` | multiple | `dict[str, Any]` for API responses | TypedDict for known structures |
| `stores/agent_store.py` | 211, 481 | `result: dict[str, Any]` | TypedDict for specific structure |

#### Medium-Priority Improvements

| Pattern | Location | Recommendation |
|---------|----------|----------------|
| Untyped `**kwargs` | 7+ widget `__init__` methods | Use `TypedDict` or explicit parameters |
| Heavy `getattr()` | `token_streamer.py:184-254` | Define protocol for streaming chunks |
| Multiple `cast()` calls | `input_area.py`, `settings_screen.py` | Fix type inference or use proper protocols |

---

## State Management Issues

### Current State: ✅ Well-Implemented

The TUI uses a **reactive state management pattern** that is well-documented and follows best practices:

```
ConversationContainer (#conversation_state) - Single source of truth
├── Owns reactive properties: running, conversation_id, confirmation_policy, etc.
├── UI widgets bind via data_bind() for auto-updates
├── Thread-safe updates via call_from_thread()
└── Clear separation: ConversationManager routes messages → Controllers update state
```

### ✅ No Mutable Default Arguments Found

Grep search confirmed no instances of `def.*=[]` or `def.*={}` patterns.

### ✅ Module-Level Constants Are Immutable

All module-level state found consists of immutable constants:
- `DEFAULT_CRITIC_THRESHOLD = 0.6` (cli_settings.py)
- `DEFAULT_LLM_BASE_URL = "https://..."` (agent_store.py)
- `COMMANDS = [...]` (commands.py) - list of tuples, effectively immutable
- `PERMISSION_OPTIONS = [...]` (confirmation.py) - PermissionOption dataclass instances

### Minor Improvements

| Issue | Location | Effort |
|-------|----------|--------|
| Consider extracting settings defaults to a single location | `stores/cli_settings.py`, `stores/agent_store.py` | Small |
| Document state flow in `acp_impl/runner.py` | Missing module docstring | Trivial |

---

## Separation of Concerns Issues

### Module Boundaries: ✅ Well-Separated

**Good practices observed:**
- No imports from `tui/` in `acp_impl/` (properly decoupled)
- No imports from `acp_impl/` in `tui/` (properly decoupled)
- `auth/` module is consumed by both ACP and TUI appropriately
- `shared/` module exists for cross-cutting utilities

### Large Files / Mixed Responsibilities

| File | Lines | Issue | Recommendation |
|------|-------|-------|----------------|
| `tui/widgets/richlog_visualizer.py` | 836 | Mixes rendering logic (collapsible creation), formatting (title building), and event processing | Extract title/formatting to `shared/`, reduce class responsibilities |
| `tui/textual_app.py` | 756 | Main app file, acceptable but could split modal management | Consider `modals/manager.py` for modal orchestration |
| `acp_impl/agent/base_agent.py` | 660 | Abstract base with many responsibilities | Well-structured for an abstract base; no change needed |
| `tui/modals/settings/settings_screen.py` | 606 | Settings UI | Could benefit from composition over inheritance |
| `stores/agent_store.py` | 532 | Agent creation/loading with I/O | Consider separating I/O operations from data structures |

### Tightly Coupled Areas

| Components | Coupling Issue | Recommendation |
|------------|----------------|----------------|
| `richlog_visualizer.py` ↔ `CliSettings` | Direct file system access in visualizer | Inject settings as parameter |
| `agent_store.py` ↔ `console` | Rich console creation at module level | Lazy initialization or injection |

---

## Code Duplication (ACP/TUI)

### Duplicated Patterns Found

#### 1. Confirmation Decision Handling (~30 lines duplicated)

**ACP** - `runner.py:113-134`:
```python
if decision == UserConfirmation.REJECT:
    conversation.reject_pending_actions(result.reason or "User rejected")
    return decision
if decision == UserConfirmation.DEFER:
    conversation.pause()
    return decision
if isinstance(policy_change, NeverConfirm):
    conversation.set_confirmation_policy(NeverConfirm())
```

**TUI** - `conversation_runner.py:158-164` + `confirmation_flow_controller.py:45-48`:
Nearly identical logic split across two files.

#### 2. Tool Title Building (~45 lines duplicated)

**ACP** - `events/utils.py:166-207` (`get_tool_title()`):
```python
if isinstance(action, FileEditorAction):
    op = "Reading" if action.command == "view" else "Editing"
    return f"{op} {action.path}"
if isinstance(action, TerminalAction):
    return f"$ {action.command}"
if isinstance(action, DelegateAction):
    return format_delegate_title(...)
```

**TUI** - `widgets/richlog_visualizer.py:471-515` (`_build_action_title()`):
Same logic with Rich markup added.

#### 3. Tool Kind Mapping (~25 lines duplicated TWICE in ACP alone!)

**ACP** - `events/utils.py:22-24` AND `events/tool_state.py:71-99`:
Both define identical `TOOL_KIND_MAPPING` dict and `get_tool_kind()`/`_compute_kind()` logic.

#### 4. Confirmation Mode Constants (~20 lines duplicated)

**ACP** - `confirmation.py:24-43` (`CONFIRMATION_MODES`)  
**TUI** - `modals/confirmation_modal.py:18-23` (`POLICY_DISPLAY_NAMES`)

Same concepts with different data structures.

#### 5. Pending Actions Retrieval (~10 lines duplicated)

Both implementations:
```python
pending_actions = ConversationState.get_unmatched_actions(conversation.state.events)
if not pending_actions:
    return UserConfirmation.ACCEPT
```

### Shared Code Opportunities

| What to Extract | Target Location | Estimated Lines Saved |
|-----------------|-----------------|----------------------|
| Tool title core logic (plain text) | `shared/action_title.py` | ~40 |
| Tool kind mapping | `shared/tool_kinds.py` | ~30 |
| Confirmation policy utilities | `shared/confirmation_policy.py` | ~35 |
| Confirmation decision handlers | `shared/confirmation_decision.py` | ~25 |
| **Total** | | **~130-150 lines** |

### Current `shared/` Module

```
shared/
├── __init__.py (8 lines)
├── conversation_summary.py (31 lines) ✅ Used by both
├── delegate_formatter.py (71 lines) ✅ Used by both
├── rich_utils.py (10 lines) ✅ Used by both
└── slash_commands.py (44 lines) ✅ Used by both
```

**Total: 164 lines.** Should grow to ~300+ lines with extracted logic.

---

## Low-Hanging Fruit

Easy fixes that can be addressed quickly:

| Fix | Location | Effort | Impact |
|-----|----------|--------|--------|
| Add return type `: None` to `__init__` methods | 20+ locations | **Trivial** | Type safety |
| Extract `TOOL_KIND_MAPPING` to shared (duplicated within ACP!) | `events/utils.py`, `events/tool_state.py` | **Trivial** | DRY principle |
| Add TypedDict for API response structures | `auth/api_client.py` | **Small** | Better IDE support |
| Type the `event` parameter in `_extract_meaningful_title` | `richlog_visualizer.py:550` | **Trivial** | Type safety |
| Type parameters in `_check_server_specs_are_equal` | `mcp_side_panel.py:212` | **Trivial** | Type safety |
| Consolidate confirmation mode constants | `acp_impl/`, `tui/modals/` | **Small** | Consistency |
| Add module docstring to `acp_impl/runner.py` | `runner.py` | **Trivial** | Documentation |
| Type `*args` in `_run_on_main_thread` | `richlog_visualizer.py:236` | **Trivial** | Type safety |

---

## Statistics

### Issue Counts by Category

| Category | Count | Severity |
|----------|-------|----------|
| Type Errors (Pyright) | 0 | ✅ None |
| Missing Return Type Annotations | ~80 | ⚠️ Low |
| `Any` Types (improvable) | ~25 | ⚠️ Low |
| Untyped `**kwargs` | 7+ | ⚠️ Low |
| Mutable Default Arguments | 0 | ✅ None |
| Global Mutable State | 0 | ✅ None |
| Cross-Module Coupling Issues | 2 | ⚠️ Low |
| Code Duplication (ACP/TUI) | ~150 lines | ⚠️ Medium |
| Large Files (>500 lines) | 5 | ⚠️ Low |

### Files by Size (Top 10)

| File | Lines |
|------|-------|
| `tui/widgets/richlog_visualizer.py` | 836 |
| `tui/textual_app.py` | 756 |
| `acp_impl/agent/base_agent.py` | 660 |
| `tui/modals/settings/settings_screen.py` | 606 |
| `stores/agent_store.py` | 532 |
| `tui/widgets/user_input/input_field.py` | 505 |
| `tui/panels/history_side_panel.py` | 466 |
| `tui/core/state.py` | 431 |
| `mcp/mcp_utils.py` | 411 |
| `auth/api_client.py` | 374 |

---

## Prioritized Action Items

### Priority 1: Quick Wins (< 1 hour each)

1. **Fix internal ACP duplication** - Extract `TOOL_KIND_MAPPING` to single location within `acp_impl/`
2. **Add return type annotations** to all `__init__` methods (`: None`)
3. **Type untyped parameters** in `richlog_visualizer.py` and `mcp_side_panel.py`
4. **Add module docstring** to `acp_impl/runner.py`

### Priority 2: Medium Effort (2-4 hours each)

5. **Extract tool title logic** - Create `shared/action_title.py` with core logic, let ACP/TUI add formatting
6. **Extract tool kind mapping** - Create `shared/tool_kinds.py`
7. **Consolidate confirmation mode constants** - Create `shared/confirmation_constants.py`
8. **Add TypedDict** for API response structures in `auth/api_client.py`

### Priority 3: Larger Refactors (4-8 hours each)

9. **Extract confirmation decision handling** - Create `shared/confirmation_decision.py`
10. **Refactor `richlog_visualizer.py`** - Split into rendering vs. formatting modules
11. **Replace `Any` types with protocols** in ACP agent classes
12. **Add type protocols** for streaming chunks in `token_streamer.py`

### Not Recommended

- Breaking up `textual_app.py` - Current structure is idiomatic for Textual apps
- Adding state management libraries - Current reactive pattern is sufficient
- Major architectural changes - Current separation is appropriate

---

## Appendix: Architecture Overview

```
openhands_cli/
├── acp_impl/          # ACP (Agent Communication Protocol) implementation
│   ├── agent/         # Local and remote agent implementations
│   ├── events/        # Event handling and streaming
│   └── utils/         # ACP-specific utilities
├── tui/               # Textual TUI implementation
│   ├── core/          # State management, controllers, runners
│   ├── modals/        # Modal screens and dialogs
│   ├── panels/        # Side panels (history, MCP, plan)
│   ├── widgets/       # Reusable UI components
│   └── utils/         # TUI-specific utilities
├── auth/              # Authentication (device flow, token storage)
├── stores/            # Persistent storage (agent config, CLI settings)
├── shared/            # Cross-cutting utilities (should grow)
├── conversations/     # Conversation persistence and display
├── mcp/               # MCP server management
└── argparsers/        # CLI argument parsing
```

**Good separation observed:**
- `acp_impl/` and `tui/` do not import each other
- `shared/` provides common utilities
- `auth/` is consumed appropriately by both implementations
- `stores/` provides data layer without UI concerns
