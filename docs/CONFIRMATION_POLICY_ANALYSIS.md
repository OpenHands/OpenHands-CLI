# TUI Confirmation Policy Control Flow Analysis

## Status: IMPLEMENTED ✅

The refactoring described in this document has been implemented. StateManager now owns the
confirmation policy, and all other components delegate to it.

## Executive Summary

This document analyzes the confirmation policy management within the **TUI subsystem only** (ignoring ACP). The analysis identifies:

1. **When** confirmation policy can be set
2. **Who** currently sets it (multiple places)
3. **Who should own** the policy (proposed: StateManager)

---

## Current State Architecture

### Source of Truth
The SDK's `BaseConversation.state.confirmation_policy` is the **actual runtime source of truth**. However, the TUI maintains shadow state that must be manually synchronized.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Current TUI State                              │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  SDK: conversation.state.confirmation_policy                    │    │
│  │       (ConfirmationPolicyBase - actual runtime behavior)        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              ↑                                          │
│                              │ manually synced                          │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  ConversationRunner._confirmation_mode_active: bool             │    │
│  │       (shadow state - used to decide run behavior)              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              ↑                                          │
│                              │ manually synced                          │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  StateManager.is_confirmation_mode: var[bool]                   │    │
│  │       (reactive state - NOT CURRENTLY USED by any widget!)      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Finding:** `StateManager.is_confirmation_mode` is defined but **not bound to any UI widget**. No widget currently reacts to confirmation mode changes.

---

## When Can Confirmation Policy Be Set?

### 1. **At App Startup** (CLI Arguments)

**Location:** `textual_app.py::main()`
```python
initial_confirmation_policy = AlwaysConfirm()  # Default
if headless or always_approve:
    initial_confirmation_policy = NeverConfirm()
elif llm_approve:
    initial_confirmation_policy = ConfirmRisky(threshold=SecurityRisk.HIGH)
```

**Flow:**
```
CLI args → main() → OpenHandsApp.__init__() → self.initial_confirmation_policy
```

### 2. **At ConversationRunner Creation** (Lazy Initialization)

**Location:** `conversation_runner.py::__init__()`

ConversationRunner is created lazily when:
- First user message is sent (`_handle_user_message`)
- `/confirm` command is used (`_handle_confirm_command`)
- Conversation is switched (`conversation_switcher.py`)

```python
# In ConversationRunner.__init__()
starting_confirmation_policy = initial_confirmation_policy or AlwaysConfirm()
self.conversation = setup_conversation(
    conversation_id,
    confirmation_policy=starting_confirmation_policy,
    ...
)
self._confirmation_mode_active = not isinstance(starting_confirmation_policy, NeverConfirm)
self._state_manager.set_confirmation_mode(self._confirmation_mode_active)
```

**Flow:**
```
create_conversation_runner() 
    → ConversationRunner.__init__()
        → setup_conversation() 
            → conversation.set_confirmation_policy()
        → self._confirmation_mode_active = ...
        → state_manager.set_confirmation_mode()
```

### 3. **Via `/confirm` Command** (User Action)

**Location:** `textual_app.py::_handle_confirm_command()` → `confirmation_modal.py`

```python
# textual_app.py
def _handle_confirm_command(self):
    current_policy = self.conversation_runner.get_confirmation_policy()
    confirmation_modal = ConfirmationSettingsModal(
        current_policy=current_policy,
        on_policy_selected=self._on_confirmation_policy_selected,
    )
    self.push_screen(confirmation_modal)

def _on_confirmation_policy_selected(self, policy):
    self.conversation_runner.set_confirmation_policy(policy)
```

**Flow:**
```
/confirm command
    → _handle_confirm_command()
        → ConfirmationSettingsModal (user selects)
            → Creates policy instance (AlwaysConfirm/NeverConfirm/ConfirmRisky)
            → on_policy_selected callback
                → conversation_runner.set_confirmation_policy()
                    → conversation.set_confirmation_policy()  ✓
                    → state_manager.set_confirmation_mode()   ✓ (but uses stale value!)
```

**BUG:** `set_confirmation_policy()` doesn't update `_confirmation_mode_active` before calling `state_manager.set_confirmation_mode()`:
```python
def set_confirmation_policy(self, confirmation_policy):
    if self.conversation:
        self.conversation.set_confirmation_policy(confirmation_policy)
        if self._state_manager:
            # BUG: _confirmation_mode_active is NOT updated here!
            self._state_manager.set_confirmation_mode(self._confirmation_mode_active)
```

### 4. **At Runtime During Confirmation** (User Decision)

**Location:** `conversation_runner.py::_handle_confirmation_request()`

When user responds to inline confirmation panel:
```python
def _handle_confirmation_request(self):
    decision = self._confirmation_callback(pending_actions)  # Shows InlineConfirmationPanel
    
    if decision == UserConfirmation.ALWAYS_PROCEED:
        self._change_confirmation_policy(NeverConfirm())
    elif decision == UserConfirmation.CONFIRM_RISKY:
        self._change_confirmation_policy(ConfirmRisky())

def _change_confirmation_policy(self, new_policy):
    self.conversation.set_confirmation_policy(new_policy)
    if isinstance(new_policy, NeverConfirm):
        self._confirmation_mode_active = False
    else:
        self._confirmation_mode_active = True
    # NOTE: Does NOT call state_manager.set_confirmation_mode()!
```

**BUG:** `_change_confirmation_policy()` updates the SDK and local state but does NOT sync to StateManager.

---

## Current Problems

### Problem 1: Manual Sync Required
Every place that changes the policy must manually sync 3 states:
1. `conversation.set_confirmation_policy()` - SDK
2. `self._confirmation_mode_active = ...` - ConversationRunner
3. `state_manager.set_confirmation_mode()` - StateManager

### Problem 2: Inconsistent Sync
- `set_confirmation_policy()` syncs SDK + StateManager but NOT `_confirmation_mode_active`
- `_change_confirmation_policy()` syncs SDK + `_confirmation_mode_active` but NOT StateManager

### Problem 3: Multiple Entry Points
Policy can be set from 4 different places:
1. CLI args → App → ConversationRunner init
2. `/confirm` command → Modal → `set_confirmation_policy()`
3. Inline confirmation → `_change_confirmation_policy()`
4. (Unused) `toggle_confirmation_mode()` → `_change_confirmation_policy()`

### Problem 4: Unused Reactive State
`StateManager.is_confirmation_mode` exists but no widget binds to it.

---

## Proposed Solution: StateManager Owns the Policy

### Design Principle
**StateManager should be the single owner of confirmation policy state.** All changes flow through StateManager, which:
1. Stores the authoritative policy
2. Syncs to SDK conversation when attached
3. Provides reactive state for UI components
4. Exposes a clean API for policy changes

### New Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Proposed Architecture                           │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  StateManager (OWNER)                                           │    │
│  │    - confirmation_policy: var[ConfirmationPolicyBase]           │    │
│  │    - _conversation: BaseConversation | None                     │    │
│  │                                                                 │    │
│  │  Methods:                                                       │    │
│  │    - set_confirmation_policy(policy)  ← Single entry point      │    │
│  │    - attach_conversation(conv)        ← Links to SDK            │    │
│  │    - detach_conversation()                                      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              │ auto-syncs on change                     │
│                              ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  SDK: conversation.state.confirmation_policy                    │    │
│  │       (synced automatically by StateManager)                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ConversationRunner:                                                    │
│  │  - Reads policy from: state_manager.confirmation_policy             │
│  │  - Sets policy via: state_manager.set_confirmation_policy()         │
│  │  - No internal _confirmation_mode_active state!                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Implementation

#### 1. Enhanced StateManager

```python
# openhands_cli/tui/core/state.py

from openhands.sdk import BaseConversation
from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmationPolicyBase,
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer

class StateManager(Container):
    # Replace boolean with actual policy object
    confirmation_policy: var[ConfirmationPolicyBase] = var(AlwaysConfirm())
    
    # Derived reactive property for simple boolean checks
    @property
    def is_confirmation_active(self) -> bool:
        """Returns True if confirmation is required (not NeverConfirm)."""
        return not isinstance(self.confirmation_policy, NeverConfirm)
    
    def __init__(self, initial_policy: ConfirmationPolicyBase | None = None, **kwargs):
        super().__init__(id="input_area", **kwargs)
        self._conversation: BaseConversation | None = None
        if initial_policy:
            self.confirmation_policy = initial_policy
    
    def attach_conversation(self, conversation: BaseConversation) -> None:
        """Attach a conversation and sync current policy to it."""
        self._conversation = conversation
        self._sync_policy_to_conversation()
    
    def detach_conversation(self) -> None:
        """Detach the current conversation."""
        self._conversation = None
    
    def set_confirmation_policy(self, policy: ConfirmationPolicyBase) -> None:
        """Set the confirmation policy. Single entry point for all policy changes.
        
        This method:
        1. Updates the reactive state (triggers UI updates)
        2. Syncs to the attached conversation (if any)
        """
        self._schedule_update("confirmation_policy", policy)
        self._sync_policy_to_conversation()
    
    def watch_confirmation_policy(
        self, old_value: ConfirmationPolicyBase, new_value: ConfirmationPolicyBase
    ) -> None:
        """React to policy changes - sync to conversation."""
        self._sync_policy_to_conversation()
    
    def _sync_policy_to_conversation(self) -> None:
        """Sync current policy to the attached conversation."""
        if self._conversation is None:
            return
        
        self._conversation.set_security_analyzer(LLMSecurityAnalyzer())
        self._conversation.set_confirmation_policy(self.confirmation_policy)
```

#### 2. Simplified ConversationRunner

```python
# openhands_cli/tui/core/conversation_runner.py

class ConversationRunner:
    def __init__(
        self,
        conversation_id: uuid.UUID,
        state_manager: StateManager,
        confirmation_callback: Callable,
        notification_callback: Callable,
        visualizer: ConversationVisualizer,
        event_callback: Callable[[Event], None] | None = None,
        *,
        env_overrides_enabled: bool = False,
        critic_disabled: bool = False,
    ):
        self._state_manager = state_manager
        self._confirmation_callback = confirmation_callback
        self._notification_callback = notification_callback
        self.visualizer = visualizer
        
        # Create conversation WITHOUT setting policy (StateManager will do it)
        self.conversation = self._create_conversation(
            conversation_id,
            visualizer=visualizer,
            event_callback=event_callback,
            env_overrides_enabled=env_overrides_enabled,
            critic_disabled=critic_disabled,
        )
        
        # Attach conversation to StateManager - this syncs the policy
        self._state_manager.attach_conversation(self.conversation)
        
        self._running = False
    
    def _create_conversation(self, conversation_id, **kwargs) -> BaseConversation:
        """Create conversation without policy (StateManager owns policy)."""
        # Similar to setup_conversation but without policy setup
        agent = load_agent_specs(str(conversation_id), ...)
        return Conversation(agent=agent, workspace=..., ...)
    
    @property
    def is_confirmation_mode_active(self) -> bool:
        """Check if confirmation mode is active (delegates to StateManager)."""
        return self._state_manager.is_confirmation_active
    
    def get_confirmation_policy(self) -> ConfirmationPolicyBase:
        """Get the current confirmation policy (from StateManager)."""
        return self._state_manager.confirmation_policy
    
    # REMOVED: set_confirmation_policy() - use state_manager directly
    # REMOVED: _change_confirmation_policy() - use state_manager directly
    # REMOVED: toggle_confirmation_mode() - use state_manager directly
    # REMOVED: _confirmation_mode_active - no longer needed
    
    def _handle_confirmation_request(self) -> UserConfirmation:
        """Handle confirmation request from user."""
        decision = self._confirmation_callback(pending_actions)
        
        if decision == UserConfirmation.REJECT:
            self.conversation.reject_pending_actions("User rejected the actions")
        elif decision == UserConfirmation.DEFER:
            self.conversation.pause()
        elif decision == UserConfirmation.ALWAYS_PROCEED:
            # Single place to change policy!
            self._state_manager.set_confirmation_policy(NeverConfirm())
        elif decision == UserConfirmation.CONFIRM_RISKY:
            self._state_manager.set_confirmation_policy(ConfirmRisky())
        
        return decision
    
    def _run_conversation_sync(self, message: Message, headless: bool = False) -> None:
        """Run the conversation synchronously."""
        self._update_run_status(True)
        try:
            self.conversation.send_message(message)
            # Use StateManager's policy state
            if self._state_manager.is_confirmation_active:
                self._run_with_confirmation()
            elif headless:
                # ... headless mode
                self.conversation.run()
            else:
                self.conversation.run()
        finally:
            self._update_run_status(False)
```

#### 3. Simplified OpenHandsApp

```python
# openhands_cli/tui/textual_app.py

class OpenHandsApp(App):
    def __init__(
        self,
        initial_confirmation_policy: ConfirmationPolicyBase | None = None,
        ...
    ):
        # Pass initial policy to StateManager
        self.state_manager = StateManager(
            initial_policy=initial_confirmation_policy or AlwaysConfirm()
        )
        ...
    
    def _on_confirmation_policy_selected(self, policy: ConfirmationPolicyBase) -> None:
        """Handle when a confirmation policy is selected from the modal."""
        # Single line - StateManager handles everything
        self.state_manager.set_confirmation_policy(policy)
        
        # Notification
        policy_name = self._get_policy_name(policy)
        self.notify(f"Confirmation policy set to: {policy_name}")
    
    def _get_policy_name(self, policy: ConfirmationPolicyBase) -> str:
        if isinstance(policy, NeverConfirm):
            return "Always approve actions (no confirmation)"
        elif isinstance(policy, AlwaysConfirm):
            return "Confirm every action"
        elif isinstance(policy, ConfirmRisky):
            return "Confirm high-risk actions only"
        return "Custom policy"
```

#### 4. Simplified ConfirmationModal

```python
# openhands_cli/tui/modals/confirmation_modal.py

class ConfirmationSettingsModal(ModalScreen):
    def __init__(
        self,
        current_policy: ConfirmationPolicyBase,
        on_policy_selected: Callable[[ConfirmationPolicyBase], None],
        **kwargs,
    ):
        # No change needed - modal already creates policy objects
        # and calls callback. StateManager handles the rest.
        ...
```

---

## Control Flow After Refactoring

### Setting Policy via `/confirm` Command
```
/confirm command
    → _handle_confirm_command()
        → ConfirmationSettingsModal (user selects)
            → Creates policy instance
            → on_policy_selected callback
                → state_manager.set_confirmation_policy(policy)
                    → Updates reactive state
                    → watch_confirmation_policy() triggered
                        → conversation.set_confirmation_policy()  ✓
                        → UI widgets auto-update via data_bind  ✓
```

### Setting Policy via Inline Confirmation
```
User selects "Always" in InlineConfirmationPanel
    → confirmation_callback(UserConfirmation.ALWAYS_PROCEED)
        → _handle_confirmation_request()
            → state_manager.set_confirmation_policy(NeverConfirm())
                → Updates reactive state
                → watch_confirmation_policy() triggered
                    → conversation.set_confirmation_policy()  ✓
                    → UI widgets auto-update via data_bind  ✓
```

---

## Summary of Changes

| Component | Before | After |
|-----------|--------|-------|
| **StateManager** | `is_confirmation_mode: bool` (unused) | `confirmation_policy: ConfirmationPolicyBase` (owns policy) |
| **ConversationRunner** | Has `_confirmation_mode_active`, `set_confirmation_policy()`, `_change_confirmation_policy()` | Delegates everything to StateManager |
| **OpenHandsApp** | Calls `conversation_runner.set_confirmation_policy()` | Calls `state_manager.set_confirmation_policy()` |
| **setup.py** | Sets policy on conversation | No longer sets policy (StateManager does it) |

---

## Benefits

1. **Single Owner:** StateManager owns the policy, no manual sync needed
2. **Automatic Sync:** Watcher pattern ensures SDK is always in sync
3. **Reactive UI:** Widgets can bind to `StateManager.confirmation_policy`
4. **Simpler ConversationRunner:** Removes 3 methods and 1 instance variable
5. **Bug-Free:** No more inconsistent state between components
