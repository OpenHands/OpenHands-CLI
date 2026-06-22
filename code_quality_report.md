# Code Quality Analysis Report

**Repository:** OpenHands-CLI  
**Analysis Date:** 2026-06-22  
**Codebase Size:** 127 Python files, ~19,432 lines of code

---

## Executive Summary

The OpenHands CLI codebase demonstrates **overall good code quality** with:
- ✅ **Zero pyright errors** (248 files analyzed, 0 errors/warnings)
- ✅ **No mutable default arguments** (common Python pitfall avoided)
- ✅ **Well-structured reactive state management** in the TUI layer
- ✅ **Existing shared modules** that extract common code

**Key Areas for Improvement:**
1. **Code duplication between ACP and TUI** implementations (~245 lines of duplicated patterns)
2. **Business logic mixed with presentation** in auth/ and stores/ modules
3. **Type annotations** could be enhanced with TypedDicts for structured data
4. **Tight coupling** between ConversationContainer and widget types

**Overall Assessment:** The codebase is maintainable and well-organized. The recommendations below are improvements, not critical fixes.

---

## Type Checking Issues

### Critical Issues: Type Errors That Could Cause Runtime Bugs
**None identified.** Pyright reports 0 errors across 248 files analyzed.

### Missing Type Hints

#### Untyped `**kwargs` Parameters (9 instances)

| File | Line | Signature |
|------|------|-----------|
| `tui/modals/history_search.py` | 85 | `def __init__(self, **kwargs) -> None:` |
| `tui/widgets/splash.py` | 78 | `def __init__(self, **kwargs) -> None:` |
| `tui/widgets/status_line.py` | 37, 142 | `def __init__(self, **kwargs) -> None:` |
| `tui/panels/mcp_side_panel.py` | 25 | `def __init__(self, agent: Agent \| None = None, **kwargs) -> None:` |
| `tui/panels/plan_side_panel.py` | 54 | `def __init__(self, app: OpenHandsApp, **kwargs) -> None:` |
| `tui/panels/confirmation_panel.py` | 19 | `def __init__(self, label: str, **kwargs) -> None:` |
| `tui/core/state.py` | 140-144 | `def __init__(..., **kwargs,) -> None:` |
| `tui/textual_app.py` | 132-142 | `def __init__(..., **kwargs,) -> None:` |

**Recommendation:** Add explicit `**kwargs: Any` for consistency and clarity.

#### Class Attributes Without Type Annotations (~35 attributes across 12 classes)

| Class | File | Missing Annotations |
|-------|------|---------------------|
| `ToolCallState` | `acp_impl/events/tool_state.py:21-34` | `tool_call_id`, `tool_name`, `is_think`, `args`, `lexer`, `started` |
| `EventSubscriber` | `acp_impl/events/event.py:58-61` | `session_id`, `conn`, `conversation` |
| `TokenBasedEventSubscriber` | `acp_impl/events/token_streamer.py:78-88` | `session_id`, `conn`, `loop`, `_streaming_tool_calls` |
| `UnbufferedJsonRpcReader` | `acp_impl/test_utils.py:34-37` | `stdout`, `buffer`, `fd` |
| `OpenHandsApiClient` | `auth/api_client.py:59-64` | `api_key`, `_headers` |
| `TokenStorage` | `auth/token_storage.py:12-25` | `config_dir`, `api_key_file` |
| `BaseHttpClient` | `auth/http_client.py:27-35` | `server_url`, `timeout` |
| `PromptHistoryStore` | `stores/prompt_history.py:24-26` | `path`, `max_entries` |
| `AgentStore` | `stores/agent_store.py:260-261` | `file_store` |
| `WorkingStatusLine` | `tui/widgets/status_line.py:37-41` | `_timer`, `_working_frame` |
| `HistorySearchScreen` | `tui/modals/history_search.py:85-89` | `history_store`, `_all_entries` |

### Type Improvement Opportunities

#### `Any` Types That Should Be TypedDicts (High Priority)

| File | Current Type | Suggested TypedDict |
|------|--------------|---------------------|
| `acp_impl/test_utils.py` | `dict[str, Any]` for JSONRPC | `JsonRpcMessage`, `JsonRpcResponse` |
| `auth/api_client.py` | `dict[str, Any]` for API responses | `UserInfo`, `UserSettings`, `ConversationInfo` |
| `stores/agent_store.py:481` | `settings: dict[str, Any]` | `AgentSettings` |
| `tui/utils/critic/refinement.py` | `dict[str, Any]` for critic features | `CriticFeature` |
| `tui/utils/critic/visualization.py` | `categorized: dict[str, Any]` | `CategorizedFeatures` |
| `shared/delegate_formatter.py:19,67` | `tasks: dict[str, Any]` | `dict[str, str]` (agent_id → task) |

**Recommended TypedDicts to Create:**

```python
# For JSONRPC (acp_impl/test_utils.py)
class JsonRpcMessage(TypedDict):
    jsonrpc: str
    method: str
    params: dict[str, Any] | None
    id: int | str | None

# For API responses (auth/api_client.py)
class UserInfo(TypedDict):
    id: str
    email: str
    name: NotRequired[str]

# For Critic features (tui/utils/critic/)
class CriticFeature(TypedDict):
    name: str
    display_name: str
    probability: float
```

---

## State Management Issues

### Current State

The codebase uses a **well-designed reactive state pattern**:

| Layer | Location | Pattern |
|-------|----------|---------|
| Persistence | `stores/` | File-backed stores with `load()`/`save()` |
| TUI State | `tui/core/state.py` | Reactive `ConversationContainer` with Textual `var` |
| Controllers | `tui/core/*_controller.py` | Single-responsibility business logic |
| Events | `tui/core/events.py` | Message-based communication |

**Positive Patterns:**
- Thread-safe state updates via `_schedule_update()`
- Pydantic validation for settings (`CliSettings`, `CriticSettings`)
- No mutable default arguments found

### Problems Identified

#### 1. Module-Level Console Instances (Global State)

| File | Line |
|------|------|
| `stores/agent_store.py` | 43-44 |
| `gui_launcher.py` | 15 |
| `auth/utils.py` | 16 |
| `conversations/viewer.py` | 12 |
| `conversations/display.py` | 11 |
| `mcp/mcp_commands.py` | 26 |
| `entrypoint.py` | 27 |

**Impact:** Harder to test, potential issues with concurrent access.

#### 2. Prop Drilling in Controller Initialization

`tui/core/conversation_switch_controller.py:24-32` receives 6+ dependencies:
```python
def __init__(
    self,
    *,
    state: ConversationContainer,
    runners: RunnerRegistry,
    notify: Callable[..., None],
    post_message: Callable[[TextualMessage], bool],
    run_worker: Callable[..., object],
    call_from_thread: Callable[..., None],
) -> None:
```

**Impact:** Boilerplate in controller creation, harder to add new controllers.

#### 3. Multiple `CliSettings.load()` Calls

Redundant file I/O:
- `tui/widgets/richlog_visualizer.py:113-116`
- `stores/agent_store.py:284`

#### 4. Token Storage Without Caching

`auth/token_storage.py` performs file I/O on every `get_api_key()` call.

### Recommendations

| Priority | Issue | Fix |
|----------|-------|-----|
| Medium | Global Console instances | Create locally or inject as dependency |
| Low | Prop drilling | Create `ConversationContext` dataclass to bundle dependencies |
| Low | CliSettings.load() | Share instance or add simple cache |
| Low | TokenStorage | Add file content caching |

---

## Separation of Concerns Issues

### Coupled Components

#### 1. Business Logic Mixed with Presentation

**Critical:** `auth/api_client.py`
| Lines | Issue |
|-------|-------|
| 162-171 | `_print_settings_summary()` - presentation in API client |
| 201-245 | `_ask_user_consent_for_overwrite()` - `input()` in validation |
| 278-304 | `create_and_save_agent_configuration()` - save + console output |
| 314-350 | `fetch_user_data_after_oauth()` - HTTP + printing + agent creation |

**Also in:**
- `auth/device_flow.py:133-183` - OAuth logic with `webbrowser.open()` and `console_print()`
- `stores/agent_store.py:173-176, 280-284` - console.print() in data store
- `setup.py:124, 144, 161` - console output during initialization

### Mixed Responsibilities

#### `AgentStore.load_or_create()` (stores/agent_store.py:289-340)

Does 5+ things:
1. Loads agent from disk
2. Creates env overrides
3. Creates agent from env vars if no disk config
4. Applies env overrides
5. Applies runtime config (tools, context, MCP, critic)

**Recommendation:** Split into `AgentLoader` and `AgentConfigurer`.

#### `SettingsScreen` (tui/modals/settings/settings_screen.py ~400 lines)

Handles: form composition, validation, loading, saving, mode switching, field dependencies, error messaging.

**Recommendation:** Extract `SettingsFormValidator`, use controller for save operations.

### Recommendations

1. **Extract presentation from auth/**
   ```python
   class AgentConfigService:
       def __init__(self, progress_callback: Callable[[str], None] | None = None):
           self._progress = progress_callback or (lambda _: None)
   ```

2. **Split AgentStore**
   ```
   stores/
   ├── agent_loader.py       # Load from disk/env
   ├── agent_configurer.py   # Apply runtime config
   └── agent_repository.py   # Persistence only
   ```

3. **Introduce service layer for auth/**
   ```
   auth/
   ├── services/
   │   ├── oauth_service.py      # OAuth flow only
   │   └── settings_sync.py      # Sync settings from cloud
   ├── api_client.py             # HTTP only
   └── commands/
       └── login.py              # Orchestration + UI
   ```

4. **Decouple ConversationContainer from widget types**
   - Move `compose()` to a dedicated `ConversationView` widget
   - Use factory/DI for widget creation

---

## Code Duplication (ACP/TUI)

### Duplicated Patterns

#### 1. Confirmation Mode/Policy Configuration (HIGH PRIORITY)

**ACP:** `acp_impl/confirmation.py:25-49`
```python
ConfirmationMode = Literal["always-ask", "always-approve", "llm-approve"]
CONFIRMATION_MODES: dict[ConfirmationMode, dict[str, str]] = {
    "always-ask": {"short": "Ask for permission...", "long": "..."},
    ...
}
```

**TUI:** `tui/modals/confirmation_modal.py:18-27`
```python
POLICY_DISPLAY_NAMES: dict[type[ConfirmationPolicyBase], str] = {
    NeverConfirm: "Always approve actions (no confirmation)",
    AlwaysConfirm: "Confirm every action",
    ConfirmRisky: "Confirm high-risk actions only",
}
```

**Estimated duplication:** ~80 lines

#### 2. Confirmation Decision Handling (HIGH PRIORITY)

**ACP:** `acp_impl/runner.py:113-135`
**TUI:** `tui/core/confirmation_flow_controller.py:38-53`, `tui/core/conversation_runner.py:158-163`

Both implement: reject handling, policy change application, pause logic.

**Estimated duplication:** ~40 lines

#### 3. Tool Title Generation (MEDIUM PRIORITY)

**ACP:** `acp_impl/events/utils.py:168-217`, `acp_impl/events/tool_state.py:128-166`
**TUI:** `tui/widgets/richlog_visualizer.py:~500-540`

All implement the same pattern:
```python
if isinstance(action, FileEditorAction):
    op = "Reading" if action.command == "view" else "Editing"
    return f"{summary}: {op} {path}" if summary else f"{op} {path}"
```

**Estimated duplication:** ~100 lines

#### 4. TOOL_KIND_MAPPING (MEDIUM PRIORITY)

`acp_impl/events/utils.py:22-26`:
```python
TOOL_KIND_MAPPING: dict[str, ToolKind] = {
    "terminal": "execute",
    "browser_use": "fetch",
    "browser": "fetch",
}
```

Used in multiple files but not centralized.

### Shared Code Opportunities

**Recommended new shared modules:**

#### 1. `shared/confirmation_policy.py`
```python
ConfirmationMode = Literal["always-ask", "always-approve", "llm-approve"]

CONFIRMATION_MODES = {
    "always-ask": {"short": "...", "policy": AlwaysConfirm},
    "always-approve": {"short": "...", "policy": NeverConfirm},
    "llm-approve": {"short": "...", "policy": ConfirmRisky},
}

def validate_confirmation_mode(mode_str: str) -> ConfirmationMode | None: ...
def get_policy_display_name(policy: ConfirmationPolicyBase) -> str: ...
def apply_confirmation_decision(conversation, decision, policy_change) -> None: ...
```

#### 2. `shared/tool_display.py`
```python
TOOL_KIND_MAPPING = {"terminal": "execute", "browser_use": "fetch", "browser": "fetch"}

def get_tool_kind(tool_name: str, action=None) -> str: ...
def get_tool_title(tool_name: str, action=None, summary=None) -> str: ...
```

### Summary Table

| Duplication Area | Files | Priority | Estimated Savings |
|------------------|-------|----------|-------------------|
| Confirmation mode config | 2 files | HIGH | ~80 lines |
| Decision handling | 3 files | HIGH | ~40 lines |
| Tool title generation | 3 files | MEDIUM | ~100 lines |
| TOOL_KIND_MAPPING | 2 files | MEDIUM | ~15 lines |

**Total estimated savings:** ~235 lines (1.2% of codebase)

---

## Low-Hanging Fruit

Easy fixes that can be addressed quickly:

| Item | Effort | Impact |
|------|--------|--------|
| Add `**kwargs: Any` to all Textual widget `__init__` | Trivial | Consistency |
| Add class-level type annotations to `ToolCallState` | Trivial | Type safety |
| Move `TOOL_KIND_MAPPING` to `shared/tool_display.py` | Small | DRY |
| Create `JsonRpcMessage` TypedDict for test_utils.py | Small | Type safety |
| Add simple caching to `TokenStorage.get_api_key()` | Small | Performance |
| Extract `CONFIRMATION_MODES` to shared module | Medium | DRY, maintainability |
| Extract tool title generation to shared module | Medium | DRY, testability |

---

## Statistics

### Issues by Category

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| Type Checking | 0 | 0 | 6 | 9 | 15 |
| State Management | 0 | 0 | 1 | 4 | 5 |
| Separation of Concerns | 0 | 2 | 3 | 2 | 7 |
| Code Duplication | 0 | 2 | 2 | 1 | 5 |
| **Total** | **0** | **4** | **12** | **16** | **32** |

### Codebase Metrics

| Metric | Value |
|--------|-------|
| Python files | 127 |
| Lines of code | ~19,432 |
| Pyright errors | 0 |
| Pyright warnings | 0 |
| Estimated duplicated code | ~235 lines (1.2%) |

---

## Prioritized Action Items

### High Priority

1. **Create `shared/confirmation_policy.py`** - Consolidate confirmation mode definitions and decision handling logic from `acp_impl/confirmation.py`, `acp_impl/runner.py`, `tui/modals/confirmation_modal.py`, and `tui/core/confirmation_flow_controller.py`

2. **Extract presentation from `auth/api_client.py`** - Move console output and user prompts to a separate command layer or use callbacks

### Medium Priority

3. **Create `shared/tool_display.py`** - Extract `get_tool_title()` and `TOOL_KIND_MAPPING` from `acp_impl/events/utils.py` and `tui/widgets/richlog_visualizer.py`

4. **Create TypedDicts for structured data** - Add `JsonRpcMessage`, `UserInfo`, `CriticFeature` types for better type safety

5. **Add class-level type annotations** - Annotate instance attributes in `ToolCallState`, `EventSubscriber`, and other classes

6. **Split `AgentStore` responsibilities** - Separate loading, configuration, and persistence concerns

### Low Priority

7. **Add `**kwargs: Any` annotations** - Consistency in Textual widget subclasses

8. **Add caching to file-based lookups** - `TokenStorage.get_api_key()`, `CliSettings.load()`

9. **Replace module-level Console instances** - Use dependency injection or local creation

10. **Create `ConversationContext` dataclass** - Reduce prop drilling in controller initialization

---

## Appendix: Existing Good Patterns

The codebase already demonstrates several good practices:

| Pattern | Location | Description |
|---------|----------|-------------|
| Shared slash commands | `shared/slash_commands.py` | `parse_slash_command()` used by both ACP and TUI |
| Delegate formatter | `shared/delegate_formatter.py` | `format_delegate_title()` shared across modules |
| User action types | `user_actions/types.py` | `UserConfirmation`, `ConfirmationResult` shared |
| Conversation protocols | `conversations/protocols.py` | Protocol classes for loose coupling |
| Reactive state | `tui/core/state.py` | Thread-safe reactive state with Textual `var` |
| Controller pattern | `tui/core/*_controller.py` | Single-responsibility controllers |
| Pydantic settings | `stores/cli_settings.py` | Validated configuration with `BaseModel` |
