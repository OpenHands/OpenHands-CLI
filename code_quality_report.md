# Code Quality Analysis Report

**Repository:** OpenHands-CLI  
**Generated:** 2026-03-16  
**Files Analyzed:** 233 Python files (~18,500 lines)

---

## Executive Summary

The OpenHands CLI codebase demonstrates **strong overall code quality** with zero pyright errors (0 errors across 233 files analyzed). The architecture shows good separation between the TUI and ACP implementations, with a clear state management pattern in the TUI layer. However, there are opportunities for improvement in:

1. **Type Specificity**: Several `Any` types and untyped `**kwargs` could be more specific
2. **Code Duplication**: Moderate duplication between ACP and TUI implementations in event handling and confirmation logic
3. **State Management**: One instance of global state that could be encapsulated
4. **Separation of Concerns**: Generally good, with a few areas where responsibilities could be clearer

**Key Strengths:**
- Zero pyright errors - excellent type safety baseline
- Well-structured reactive state management in TUI (`ConversationContainer`)
- Clear controller pattern in TUI (`ConversationManager`, `*Controller` classes)
- Shared modules (`openhands_cli/shared/`) already extract common utilities
- Consistent use of Pydantic for settings and data models

---

## Type Checking Issues

### Critical Issues
**None** - Pyright reports 0 errors, 0 warnings, 0 information items.

### Missing Type Hints

| Location | Issue | Severity |
|----------|-------|----------|
| `tui/widgets/user_input/input_field.py:146` | `**kwargs` untyped | Low |
| `tui/widgets/splash.py:78` | `**kwargs` untyped | Low |
| `tui/widgets/status_line.py:37,142` | `**kwargs` untyped | Low |
| `tui/panels/plan_side_panel.py:54` | `**kwargs` untyped | Low |
| `tui/panels/mcp_side_panel.py:25` | `**kwargs` untyped | Low |
| `tui/panels/confirmation_panel.py:19` | `**kwargs` untyped | Low |
| `tui/modals/settings/components/*.py` | `**kwargs` untyped | Low |

**Note:** These `**kwargs` parameters in widget `__init__` methods are passed to parent Textual widgets, making them difficult to type precisely without coupling to Textual internals.

### Type Improvement Opportunities

| Location | Current Type | Suggested Improvement |
|----------|--------------|----------------------|
| `stores/agent_store.py:203` | `dict[str, Any]` | Consider `TypedDict` for structured result |
| `stores/agent_store.py:454` | `settings: dict[str, Any]` | Define `SettingsDict` TypedDict |
| `mcp/mcp_utils.py:375` | `dict[str, Any]` return | Define `ConfigStatus` TypedDict |
| `acp_impl/test_utils.py:39` | `dict[str, Any] | None` | Define `JsonRpcMessage` TypedDict |
| `conversations/store/local.py:197` | `event_data: dict[str, Any]` | Consider Protocol or TypedDict |
| `shared/delegate_formatter.py:19` | `tasks: dict[str, Any] | None` | More specific task type |

### `type: ignore` Comments

Only 2 instances found, both justified:

1. `tui/widgets/collapsible.py:327` - Query result typing with Textual
2. `tui/utils/critic/feedback.py:14` - Optional Posthog import

---

## State Management Issues

### Current State Architecture

**Good Practices Identified:**
- `ConversationContainer` (state.py) - Reactive state holder using Textual's `var` system
- `CliSettings` (cli_settings.py) - Pydantic model with file persistence
- `AgentStore` (agent_store.py) - Encapsulated agent configuration management
- `RunnerRegistry` - Caches runners by conversation_id

### Problems Identified

#### 1. Global State in ACP Resources
**Location:** `openhands_cli/acp_impl/utils/resources.py:38-47`

```python
_ACP_CACHE_DIR: Path | None = None

def get_acp_cache_dir() -> Path:
    global _ACP_CACHE_DIR
    if _ACP_CACHE_DIR is None:
        _ACP_CACHE_DIR = Path.home() / ".openhands" / "cache" / "acp"
        _ACP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _ACP_CACHE_DIR
```

**Issue:** Uses module-level global with lazy initialization pattern.  
**Impact:** Low - Only one instance, thread-safe for reads after initialization.  
**Recommendation:** Consider using `@functools.lru_cache(maxsize=1)` for cleaner lazy initialization.

#### 2. Potential Prop Drilling

The `env_overrides_enabled` and `critic_disabled` flags are passed through multiple layers:
- `OpenHandsApp.__init__` → `RunnerFactory` → `ConversationRunner` → `setup_conversation` → `load_agent_specs` → `AgentStore.load_or_create`

**Impact:** Medium - Adds parameters to many function signatures.  
**Recommendation:** Consider a `RuntimeConfig` dataclass to bundle these flags.

### Recommendations

1. **Bundle Configuration Flags**
   ```python
   @dataclass
   class RuntimeConfig:
       env_overrides_enabled: bool = False
       critic_disabled: bool = False
       headless_mode: bool = False
   ```

2. **Replace Global with Cached Function**
   ```python
   @functools.lru_cache(maxsize=1)
   def get_acp_cache_dir() -> Path:
       path = Path.home() / ".openhands" / "cache" / "acp"
       path.mkdir(parents=True, exist_ok=True)
       return path
   ```

---

## Separation of Concerns Issues

### Well-Separated Components

| Module | Responsibility | Quality |
|--------|----------------|---------|
| `auth/` | Authentication flows, token management | ✅ Clean |
| `stores/` | Persistent settings, agent configuration | ✅ Clean |
| `tui/core/` | State management, controllers | ✅ Clean |
| `tui/widgets/` | UI components | ✅ Clean |
| `acp_impl/events/` | Event handling for ACP | ✅ Clean |
| `conversations/` | Conversation persistence protocols | ✅ Clean |

### Areas for Improvement

#### 1. `setup.py` Mixes Configuration and Console Output
**Location:** `openhands_cli/setup.py:118-152`

```python
def setup_conversation(...) -> BaseConversation:
    console = Console()
    console.print("Initializing agent...", style="white")
    # ... setup logic ...
    console.print(f"✓ Agent initialized with model: {agent.llm.model}", style="green")
```

**Issue:** `setup_conversation` mixes business logic (creating conversation) with presentation (console output).  
**Impact:** Low - Makes testing harder, couples setup to Rich console.  
**Recommendation:** Accept optional `progress_callback` or use logging instead.

#### 2. Large `OpenHandsApp` Class (716 lines)
**Location:** `openhands_cli/tui/textual_app.py`

The main App class handles:
- Screen/modal management
- Global key bindings
- Side panel toggling
- Conversation lifecycle
- UI event routing
- Settings management

**Impact:** Medium - Large classes are harder to test and maintain.  
**Recommendation:** Already partially mitigated by delegation to `ConversationManager` and controllers. Consider extracting side panel management to a dedicated component.

#### 3. `richlog_visualizer.py` is 851 Lines
**Location:** `openhands_cli/tui/widgets/richlog_visualizer.py`

**Impact:** Medium - Long file handling multiple event types.  
**Recommendation:** Consider splitting into separate handlers per event type using a visitor pattern.

### Architecture Boundaries

| Boundary | Status | Notes |
|----------|--------|-------|
| TUI ↔ ACP | ✅ Clear | Separate implementation directories |
| UI ↔ Business Logic | ✅ Clear | Controllers separate from widgets |
| Persistence ↔ Business Logic | ✅ Clear | `stores/`, `conversations/store/` |
| Auth ↔ Core | ✅ Clear | `auth/` self-contained |

---

## Code Duplication (ACP vs TUI)

### Duplicated Patterns Identified

#### 1. Confirmation Mode Handling

| Pattern | ACP Location | TUI Location | Duplication Level |
|---------|--------------|--------------|-------------------|
| Mode definitions | `acp_impl/confirmation.py:29-49` | `tui/core/confirmation_policy_service.py` | Low (different implementations) |
| Policy application | `acp_impl/slash_commands.py:137-164` | TUI uses policy objects directly | Low |
| User decision handling | `acp_impl/runner.py:81-139` | `tui/core/conversation_runner.py:138-190` | **Medium** |

**Key Duplication:** Both `acp_impl/runner.py:_handle_confirmation_request` and `tui/core/conversation_runner.py:_execute_conversation` implement similar logic for handling `UserConfirmation` decisions and policy changes.

#### 2. Conversation Execution Loop

**ACP:** `acp_impl/runner.py:26-79`
```python
async def run_conversation_with_confirmation(...):
    while True:
        await asyncio.to_thread(conversation.run)
        if conversation.state.execution_status == FINISHED:
            break
        elif ... == WAITING_FOR_CONFIRMATION:
            user_confirmation = await _handle_confirmation_request(...)
            if user_confirmation == UserConfirmation.DEFER:
                return
        elif ... == PAUSED:
            return
```

**TUI:** `tui/core/conversation_runner.py:138-190`
```python
def _execute_conversation(...):
    # Similar pattern but synchronous
    self.conversation.run()
    if ... == WAITING_FOR_CONFIRMATION:
        self._request_confirmation()
    # ...
```

**Duplication Level:** Medium - Core loop logic is similar.

#### 3. Tool Title/Kind Formatting

| Function | ACP Location | TUI Location |
|----------|--------------|--------------|
| `get_tool_kind` | `acp_impl/events/utils.py:146-165` | Similar in `richlog_visualizer.py` (implicit) |
| `get_tool_title` | `acp_impl/events/utils.py:168-209` | Different approach in visualizer |

#### 4. Delegate Title Formatting
**Already shared:** `openhands_cli/shared/delegate_formatter.py` - Good example of proper extraction.

### Shared Code Opportunities

#### High Priority (Should Extract)

1. **Confirmation Decision Handler**
   Extract common logic for handling `UserConfirmation` decisions:
   ```python
   # openhands_cli/shared/confirmation_handler.py
   def apply_confirmation_decision(
       conversation: BaseConversation,
       decision: UserConfirmation,
       policy_change: ConfirmationPolicyBase | None,
       reason: str,
   ) -> bool:  # Returns True if should continue
       if decision == UserConfirmation.REJECT:
           conversation.reject_pending_actions(reason)
           return True
       if decision == UserConfirmation.DEFER:
           conversation.pause()
           return False
       if isinstance(policy_change, NeverConfirm):
           conversation.set_confirmation_policy(NeverConfirm())
       elif isinstance(policy_change, ConfirmRisky):
           conversation.set_confirmation_policy(policy_change)
       return True
   ```

2. **Conversation Summary Logic**
   Both `tui/core/conversation_runner.py:269-289` and `tui/core/state.py:214-234` have nearly identical `get_conversation_summary` methods.

#### Medium Priority

3. **Tool Kind/Title Utilities**
   Consider moving `acp_impl/events/utils.py` tool formatting utilities to shared if TUI needs them.

4. **CONFIRMATION_MODES Definitions**
   `acp_impl/confirmation.py:29-49` could be shared if TUI needs mode descriptions.

### Current Shared Module Content

| File | Purpose | Status |
|------|---------|--------|
| `shared/slash_commands.py` | `parse_slash_command()` | ✅ Used by ACP |
| `shared/delegate_formatter.py` | `format_delegate_title()` | ✅ Used by both |

---

## Low-Hanging Fruit

### Trivial Fixes (< 30 min each)

| Issue | Location | Fix |
|-------|----------|-----|
| Replace global with `lru_cache` | `acp_impl/utils/resources.py:38-47` | Use `@functools.lru_cache(maxsize=1)` |
| Remove duplicate `get_conversation_summary` | `tui/core/state.py` vs `conversation_runner.py` | Delegate one to the other |
| Add TypedDict for `ConfigStatus` | `mcp/mcp_utils.py:375` | Define explicit return type |

### Small Fixes (1-2 hours each)

| Issue | Location | Fix |
|-------|----------|-----|
| Extract confirmation decision handler | `acp_impl/runner.py`, `tui/core/conversation_runner.py` | Create shared function |
| Bundle runtime config flags | Multiple files | Create `RuntimeConfig` dataclass |
| Remove console output from `setup.py` | `setup.py:118-152` | Use callback or logging |

### Medium Fixes (2-4 hours each)

| Issue | Location | Fix |
|-------|----------|-----|
| Extract event handler utilities | `tui/widgets/richlog_visualizer.py` | Split into event-type modules |
| Define TypedDicts for settings | `stores/agent_store.py` | Improve type safety |

---

## Statistics

### Issue Counts by Category

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| Type Checking | 0 | 0 | 6 | 8 | 14 |
| State Management | 0 | 0 | 2 | 1 | 3 |
| Separation of Concerns | 0 | 0 | 2 | 1 | 3 |
| Code Duplication | 0 | 1 | 3 | 2 | 6 |
| **Total** | **0** | **1** | **13** | **12** | **26** |

### File Size Analysis

| Threshold | Files | Action Recommended |
|-----------|-------|-------------------|
| > 500 lines | 5 | Consider splitting |
| > 300 lines | 12 | Review for cohesion |
| < 100 lines | 45+ | Good module size |

**Largest Files:**
1. `tui/widgets/richlog_visualizer.py` - 851 lines
2. `tui/textual_app.py` - 716 lines
3. `acp_impl/agent/base_agent.py` - 660 lines
4. `tui/modals/settings/settings_screen.py` - 550 lines
5. `stores/agent_store.py` - 505 lines

---

## Prioritized Action Items

### Immediate (Before Next Release)

1. ✅ **No critical type errors** - No blocking issues

### Short-Term (Next Sprint)

2. **Extract shared confirmation decision handler** (1-2h)
   - Creates `openhands_cli/shared/confirmation_handler.py`
   - Reduces duplication between ACP and TUI confirmation flows

3. **Consolidate `get_conversation_summary`** (30min)
   - One implementation, one location

4. **Replace global `_ACP_CACHE_DIR` with `lru_cache`** (15min)
   - Cleaner pattern, same semantics

### Medium-Term (Next Month)

5. **Create `RuntimeConfig` dataclass** (2h)
   - Bundles `env_overrides_enabled`, `critic_disabled`, `headless_mode`
   - Reduces parameter passing through call chains

6. **Add TypedDicts for untyped dicts** (2-3h)
   - `stores/agent_store.py` settings dict
   - `mcp/mcp_utils.py` config status
   - `conversations/store/local.py` event data

7. **Refactor `richlog_visualizer.py`** (4h)
   - Extract event handlers into separate modules
   - Reduces file size from 851 to ~200-300 lines per file

### Long-Term (Backlog)

8. **Remove console output from `setup.py`** (1h)
   - Use progress callback or logging
   - Improves testability

9. **Extract side panel management from `OpenHandsApp`** (4h)
   - Creates dedicated panel coordinator
   - Reduces App class size

10. **Document architecture decisions** (2h)
    - Add ADR for state management pattern
    - Add ADR for ACP vs TUI separation

---

## Recommendations Summary

1. **Maintain current type safety** - Zero pyright errors is excellent; keep it
2. **Prioritize shared extraction** - Confirmation handler duplication is the highest-impact fix
3. **Consider `RuntimeConfig` pattern** - Reduces parameter drilling
4. **Monitor file sizes** - Break up files approaching 500+ lines
5. **Continue using shared/** - The pattern works well, extend it for confirmation logic
