# OpenHands CLI — Deep Architecture Reference

> Generated: 2026-03-02 | For AI agents working on this codebase.
> Covers the 5 critical knowledge gaps not documented elsewhere.

---

## Table of Contents

1. [ACP System Architecture](#1-acp-system-architecture)
2. [Settings Load Pipeline](#2-settings-load-pipeline)
3. [Confirmation & Security Policy](#3-confirmation--security-policy)
4. [Critic & Iterative Refinement Loop](#4-critic--iterative-refinement-loop)
5. [Threading Model](#5-threading-model)
6. [Key Code Paths](#6-key-code-paths)
7. [Key Interfaces Reference](#7-key-interfaces-reference)

---

## 1. ACP System Architecture

The ACP (Agent Communication Protocol) system lives in `openhands_cli/acp_impl/` and provides IDE integration (Zed, and any ACP-compatible editor) via JSON-RPC 2.0 over stdio.

### 1.1 Agent Hierarchy

```
acp.Agent (ACPAgent from SDK)     ABC
         \                        /
    BaseOpenHandsACPAgent            (acp_impl/agent/base_agent.py:73, abstract)
          /              \
LocalOpenHandsACPAgent    OpenHandsCloudACPAgent
(local_agent.py:36)       (remote_agent.py:37)
```

**When each is used:**
- `LocalOpenHandsACPAgent` — Default (`cloud=False`). Local filesystem workspace, conversation state in `~/.openhands/conversations/`. Supports streaming.
- `OpenHandsCloudACPAgent` — When `cloud=True`. Uses `OpenHandsCloudWorkspace` with remote sandboxes. No streaming support. Overrides `prompt()` to detect dead workspaces and re-verify/recreate sandbox state before continuing.

Selection happens in `agent/launcher.py:run_acp_server()` based on the `cloud` flag.

### 1.2 Abstract Contract (`BaseOpenHandsACPAgent`)

| Abstract Method | Signature | Purpose |
|---|---|---|
| `agent_type` (property) | `-> AgentType` | Returns `"local"` or `"remote"` |
| `_get_or_create_conversation` | `(session_id, working_dir, mcp_servers, is_resuming) -> BaseConversation` | Creates or retrieves a conversation. Local uses cache; remote skips cache when resuming and re-verifies sandbox via cloud API. |
| `_cleanup_session` | `(session_id) -> None` | Local: no-op. Remote: closes workspace + conversation. |
| `_is_authenticated` | `() -> bool` | Local: calls `load_agent_specs()` (valid local setup). Remote: validates cloud API token. |

### 1.3 Session Lifecycle

```
Both agents' new_session() override base class to pre-authenticate:
  ├─ await self._is_authenticated() — raises auth_required if not authenticated
  └─ [local only] resolve effective_working_dir = working_dir or cwd or Path.cwd()

ACP client calls new_session(cwd, mcp_servers, working_dir?)
  │
  ├─ Determine session_id:
  │    ├─ if self._resume_conversation_id → use it, set is_resuming=True
  │    └─ else → uuid.uuid4()
  │
  ├─ _get_or_create_conversation(session_id, working_dir, mcp_servers, is_resuming)
  │    └─ [Local] _setup_conversation() → load_agent_specs() → Conversation(...)
  │
  ├─ if is_resuming AND conversation.state.events:
  │     EventSubscriber replays all historical events to ACP client
  │
  ├─ asyncio.create_task(send_available_commands(session_id))  [fire-and-forget]
  └─ return NewSessionResponse(session_id, modes)

ACP client calls prompt(content, session_id)
  │
  ├─ _get_or_create_conversation(session_id) [from cache]
  ├─ Parse slash commands (/help, /confirm) → short-circuit if matched
  ├─ conversation.send_message(message)
  ├─ run_task = asyncio.create_task(run_conversation_with_confirmation(...))
  │    [tracked in self._running_tasks for cancellation]
  ├─ await run_task  ← blocks until turn completes
  └─ return PromptResponse(stop_reason="end_turn")

ACP client calls load_session(cwd, mcp_servers, session_id)
  └─ Same replay pattern as new_session resume — see Section 6.3 for details.
```

### 1.4 Two Event Delivery Paths

Controlled by `streaming_enabled` in `LocalOpenHandsACPAgent._setup_conversation()`:

**Path A: Non-Streaming (`EventSubscriber` in `events/event.py`)**
- Used when `streaming_enabled=False` or by `OpenHandsCloudACPAgent` (always).
- SDK fires `sync_callback(event)` → `asyncio.run_coroutine_threadsafe(subscriber(event), loop)`.
- `EventSubscriber.__call__` dispatches by event type: `ActionEvent` → sends thought/reasoning text, then tool call start (except `ThinkAction`/`FinishAction`, which map to thought/message updates without tool-call start); `ObservationEvent` → sends tool progress; `MessageEvent` → sends agent message (user-role messages are suppressed). Also handles `SystemPromptEvent`, `PauseEvent`, `Condensation`, `CondensationRequest` (via `SharedEventHandler`), plus `UserRejectObservation` and `AgentErrorEvent` (→ tool call failed status).
- Skips `ConversationStateUpdateEvent` (internal state, not forwarded to client).

**Path B: Streaming (`TokenBasedEventSubscriber` in `events/token_streamer.py`)**
- Used when `streaming_enabled=True` AND `not agent.llm.uses_responses_api()`.
- Two entry points from separate source threads:
  1. **Token-level**: `on_token(chunk)` from LLM streaming → `_schedule_update()` → `run_coroutine_threadsafe` → real-time `AgentMessageChunk` updates.
  2. **Event-level**: `sync_callback(event)` from SDK callback thread → `token_subscriber.unstreamed_event_handler(event)` — handles completed events after streaming finishes and resets header state for next response.
- Uses `ToolCallState` (`events/tool_state.py`) per streaming tool call to track incremental arg parsing with `has_valid_skeleton` gate (prevents flickering).

**`SharedEventHandler` (`events/shared_event_handler.py`)**
- Shared logic used by both subscriber types via the `_ACPContext` protocol.
- Handles: `ThinkAction` → thought text, `FinishAction` → agent message, other actions → `start_tool_call(...)`, observations (except Think/Finish observations) → `send_tool_progress(...)`, `TaskTrackerObservation` → `AgentPlanUpdate`.

### 1.5 Thread Bridging Pattern

The SDK's `conversation.run()` is synchronous and executes in a worker thread. ACP event delivery is async. The bridge:

```python
# local_agent.py:159-172
loop = asyncio.get_event_loop()          # Capture the async event loop

def sync_callback(event: Event) -> None: # Called from SDK worker thread
    if streaming_enabled:
        asyncio.run_coroutine_threadsafe(
            token_subscriber.unstreamed_event_handler(event), loop)
    else:
        asyncio.run_coroutine_threadsafe(subscriber(event), loop)
```

Additionally, `TokenBasedEventSubscriber._schedule_update()` bridges from the LLM streaming thread:
```python
# token_streamer.py:226-239
def _schedule_update(self, update):
    async def _send():
        await self.conn.session_update(session_id=..., update=update, ...)
    if self.loop.is_running():
        asyncio.run_coroutine_threadsafe(_send(), self.loop)
    else:
        self.loop.run_until_complete(_send())  # defensive fallback
```

**All bridge sites:**

| Location | Sync Source | Async Target |
|---|---|---|
| `local_agent.py:168-172` | SDK callback thread | `subscriber(event)` or `token_subscriber.unstreamed_event_handler(event)` |
| `remote_agent.py:235` | SDK callback thread | `subscriber(event)` |
| `token_streamer.py:237` | LLM stream thread | `conn.session_update(...)` |

---

## 2. Settings Load Pipeline

### 2.1 Config Files on Disk

| File | Default Path | Contains | Env Override |
|---|---|---|---|
| `agent_settings.json` | `~/.openhands/agent_settings.json` | LLM model, API key, base_url, condenser | `OPENHANDS_PERSISTENCE_DIR` |
| `cli_config.json` | `~/.openhands/cli_config.json` | UI toggles, critic settings | `PERSISTENCE_DIR` |
| `mcp.json` | `~/.openhands/mcp.json` | Enabled MCP servers | `OPENHANDS_PERSISTENCE_DIR` |
| `hooks.json` | `~/.openhands/hooks.json` or `{work_dir}/.openhands/hooks.json` | Pre/post-action hooks | `OPENHANDS_WORK_DIR` (for cwd lookup) |
| `base_state.json` | `~/.openhands/conversations/<uuid>/base_state.json` | Tools snapshot at conversation creation | `OPENHANDS_CONVERSATIONS_DIR` |

Notes:
- `cli_config.json` uses `PERSISTENCE_DIR` while `agent_settings.json` uses `OPENHANDS_PERSISTENCE_DIR` — a historical discrepancy. Both default to `~/.openhands`.
- Additional env vars affect derived paths: `OPENHANDS_CONVERSATIONS_DIR` overrides the conversations directory (default: `{persistence_dir}/conversations`), and `OPENHANDS_WORK_DIR` overrides the working directory used for skill loading (default: `cwd`).
- `mcp.json` has no dedicated env override — it inherits `OPENHANDS_PERSISTENCE_DIR`.

### 2.2 What Is Persisted vs. Derived at Runtime

| Field | Persisted? | Source |
|---|---|---|
| `agent.llm` (model, api_key, base_url, timeout) | **Yes** — `agent_settings.json` | User setup or settings screen |
| `agent.condenser` | **Yes** — `agent_settings.json` | Created alongside LLM |
| `agent.tools` | **No** — derived | `base_state.json` (resume) or `get_default_cli_tools()` (new) |
| `agent.mcp_config` | **No** — derived | `~/.openhands/mcp.json` via `list_enabled_servers()` |
| `agent.agent_context` | **No** — derived | `load_project_skills(get_work_dir())` + OS description |
| `agent.critic` | **No** — derived | Auto-derived from `llm.base_url` pattern match |
| `agent.llm.litellm_extra_body` | **No** — derived | Added if using OpenHands proxy |
| Hooks (`HookConfig`) | **No** — read each time | `hooks.json` loaded in `setup_conversation()` |

### 2.3 Why Tools Are in `base_state.json`, Not `agent_settings.json`

Tools must match the conversation they were created with. From the code:

> "When resuming a conversation, we should use the tools that were available when the conversation was created, not the current default tools. This ensures consistency and prevents issues with tools that weren't available in the original conversation (e.g., delegate tool)."

The mechanism:
1. At conversation creation, the SDK writes `base_state.json` with the tool list.
2. On resume, `AgentStore._resolve_tools(session_id)` calls `get_persisted_conversation_tools(conversation_id)` which reads that file.
3. For new conversations, `get_default_cli_tools()` provides: `TerminalTool`, `FileEditorTool`, `TaskTrackerTool`, `DelegateTool`.

### 2.4 Complete Load Chain

```
entrypoint.py: main()
  └─ textual_app.main()
       └─ OpenHandsApp.__init__()
            ├─ CliSettings.load()                     # reads cli_config.json
            │   └─ _migrate_legacy_settings()         # auto-saves if migrated
            ├─ ConversationContainer(
            │       initial_confirmation_policy=...,
            │       initial_critic_settings=cli_settings.critic)
            ├─ RunnerFactory(env_overrides_enabled, critic_disabled, ...)
            └─ ConversationManager(state, runner_factory, store_service, ...)
                 └─ RunnerRegistry(factory=runner_factory, ...)

  [User sends first message OR resume ID provided]

  RunnerRegistry.get_or_create(conversation_id)
    └─ RunnerFactory.create(conversation_id, ...)
         └─ ConversationRunner.__init__()
              └─ setup_conversation(conversation_id, ...)  # module fn in setup.py
                   ├─ load_agent_specs(session_id, ...)
                   │    └─ AgentStore().load_or_create(session_id, ...)
                   │         │
                   │         ├─ load_from_disk()          → Agent from agent_settings.json
                   │         ├─ [if --override-with-envs] → apply LLM_API_KEY/MODEL/BASE_URL
                   │         └─ _apply_runtime_config():
                   │              ├─ _resolve_tools()     → base_state.json or defaults
                   │              ├─ _with_llm_metadata() → litellm_extra_body if proxy
                   │              ├─ _build_agent_context()→ skills + OS info
                   │              ├─ list_enabled_servers()→ mcp.json
                   │              ├─ _maybe_build_condenser() → re-tag condenser LLM metadata
                   │              └─ CliSettings.load()   → get_default_critic()
                   │                                       → regex match → APIBasedCritic or None
                   ├─ HookConfig.load(get_work_dir())     → hooks.json
                   └─ Conversation(agent, workspace, persistence_dir, hook_config, ...)
    └─ runner.replay_historical_events()      # no-op for new; replays on resume/switch
```

### 2.5 Env Overrides

When `--override-with-envs` is passed:
- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` are read from environment.
- If persisted agent exists: partial override allowed (e.g., only API key).
- If no persisted agent: both `LLM_API_KEY` and `LLM_MODEL` required (raises `MissingEnvironmentVariablesError`).
- Overrides are **never persisted** to disk.

### 2.6 Migration Path for New Settings Fields

**`CliSettings` / `CriticSettings`**: Add field with default value. For restructuring, add a case in `_migrate_legacy_settings()` — migration auto-saves on load.

`CliSettings` also contains non-critic UI fields (`default_cells_expanded`, `auto_open_plan_panel`) which follow the same Pydantic defaults-on-missing-field pattern.

**`agent_settings.json`**: Pydantic handles schema evolution automatically — missing fields use defaults, extra fields are ignored. No explicit migration needed.

---

## 3. Confirmation & Security Policy

### 3.1 Two Parallel Flows

**TUI Flow (interactive terminal):**
```
ConversationRunner._execute_conversation()     [runs in thread pool]
  → conversation.run() returns with WAITING_FOR_CONFIRMATION
  → [guard: only if is_confirmation_mode_active (policy is not NeverConfirm)]
  → _request_confirmation()
  → self._message_pump.post_message(ShowConfirmationPanel(pending_actions))
  → [bubbles to] ConversationManager._on_show_confirmation_panel()
  → ConfirmationFlowController.show_panel(count)
  → state.set_pending_action_count(count)         [reactive: mounts InlineConfirmationPanel]
  → User selects option in InlineConfirmationPanel
  → post_message(ConfirmationDecision(decision))
  → [bubbles to] ConversationManager._on_confirmation_decision()
  → ConfirmationFlowController.handle_decision(decision)
  → [if ALWAYS_PROCEED or CONFIRM_RISKY] ConfirmationPolicyService.set_policy(policy)  [dual-write]
  → run_worker(runner.resume_after_confirmation(decision))    [new worker; not a while loop]
```

**ACP Flow (IDE integration):**
```
run_conversation_with_confirmation()              [async]
  → [pre-check] if already WAITING_FOR_CONFIRMATION:
      → _handle_confirmation_request() first (resume case)
  → while True:
      → await asyncio.to_thread(conversation.run)
      → WAITING_FOR_CONFIRMATION
      → _handle_confirmation_request()
  → await ask_user_confirmation_acp(conn, session_id, pending_actions)
    → conn.request_permission(...)                 [ACP protocol to IDE]
    → returns ConfirmationResult(decision, policy_change)
  → [if REJECT] conversation.reject_pending_actions() → loop continues
  → [if DEFER]  conversation.pause() → return
  → [if policy_change] conversation.set_confirmation_policy(policy)   [single write, no ConversationContainer]
  → loop continues
```

| Aspect | TUI | ACP |
|---|---|---|
| User prompt | `InlineConfirmationPanel` widget | `conn.request_permission()` protocol call |
| Policy write | **Dual-write**: SDK conversation + `ConversationContainer` reactive | **Single write**: SDK conversation only |
| Confirmation guard | Only when `is_confirmation_mode_active` | Always when status is `WAITING_FOR_CONFIRMATION` |
| Blocking style | Worker chaining (new worker per decision) | Async while loop |

**ACP Error Handling**: If `conn.request_permission()` throws an exception, the ACP flow falls back to `DEFER` (pauses conversation safely). If the IDE returns a `DeniedOutcome` (user cancelled), it maps to `REJECT`.

### 3.2 Policy Hierarchy

Imported from SDK: `from openhands.sdk.security.confirmation_policy import ConfirmationPolicyBase`

| Policy | Behavior | Maps To |
|---|---|---|
| `AlwaysConfirm()` | Every action requires confirmation | "always-ask" (default) |
| `NeverConfirm()` | All actions auto-approved | "always-approve" |
| `ConfirmRisky(threshold=SecurityRisk.HIGH)` | Only high-risk actions need confirmation | "llm-approve" |

> **Note on threshold usage**:
> - ACP `risk_based` path explicitly passes `ConfirmRisky(threshold=SecurityRisk.HIGH)`.
> - TUI startup `--llm-approve` also explicitly passes `ConfirmRisky(threshold=SecurityRisk.HIGH)`.
> - `ConfirmationFlowController` and `ConfirmationSettingsModal` call `ConfirmRisky()` relying on SDK defaults.

### 3.3 `ConversationExecutionStatus` State Machine

**ACP path (explicit while loop):**
```
conversation.run() returns
    ├── FINISHED → break (done)
    ├── WAITING_FOR_CONFIRMATION → _handle_confirmation_request()
    │     ├── ACCEPT → loop continues (run again)
    │     ├── REJECT → reject_pending_actions() → loop continues
    │     └── DEFER → conversation.pause() → return
    └── PAUSED → return (cancelled externally)
```

**TUI path (worker chaining):**
```
conversation.run() returns
    ├── FINISHED → worker ends
    ├── WAITING_FOR_CONFIRMATION (if confirmation mode active)
    │     → _request_confirmation() → ShowConfirmationPanel
    │     → user decision → new worker resume_after_confirmation(decision)
    │           ├── ACCEPT / policy change → conversation.run() again
    │           ├── REJECT → reject_pending_actions() → conversation.run() again
    │           └── DEFER → conversation.pause() → early return
    └── PAUSED → worker ends
```

### 3.4 Dual-Write Requirement (TUI Only)

`ConfirmationPolicyService.set_policy()` (`tui/core/confirmation_policy_service.py`):

```python
def set_policy(self, policy: ConfirmationPolicyBase) -> None:
    runner = self._runners.current
    if runner is not None and runner.conversation is not None:
        runner.conversation.set_confirmation_policy(policy)  # Write 1: SDK
    self._state.confirmation_policy = policy                 # Write 2: reactive var
```

Both writes are necessary:
- **SDK write**: Makes the policy take effect for tool call evaluation.
- **Reactive write**: Drives UI state (status line, settings modal, `is_confirmation_active` property).

### 3.5 Key Types

```python
# openhands_cli/user_actions/types.py
class UserConfirmation(Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"
    ALWAYS_PROCEED = "always_proceed"
    CONFIRM_RISKY = "confirm_risky"

class ConfirmationResult(BaseModel):   # ACP path only
    decision: UserConfirmation
    policy_change: ConfirmationPolicyBase | None = None
    reason: str = ""
```

---

## 4. Critic & Iterative Refinement Loop

### 4.1 Auto-Configuration Gating

The critic is **only available** when using the OpenHands LLM proxy:

```python
# stores/agent_store.py:80-119
def get_default_critic(llm, *, enable_critic=True):
    if not enable_critic: return None
    if llm.base_url is None or llm.api_key is None: return None
    pattern = r"^https?://llm-proxy\.[^./]+\.all-hands\.dev"
    if not re.match(pattern, llm.base_url): return None
    try:
        return APIBasedCritic(
            server_url=f"{llm.base_url.rstrip('/')}/vllm",
            api_key=llm.api_key, model_name="critic")
    except Exception:
        return None
```

The critic is **never persisted** — it is derived fresh on every `load_or_create()` call.

### 4.2 Full Refinement Cycle

```
Agent completes turn → SDK attaches CriticResult to event
  ↓
ConversationVisualizer.on_event()                     [richlog_visualizer.py]
  └── if critic_result: _handle_critic_result(critic_result)
  ↓
ConversationVisualizer._handle_critic_result()        [richlog_visualizer.py]
  ├── Guard: skip if critic_settings.enable_critic is False
  ├── send_critic_inference_event(...)                 [telemetry]
  ├── Render UI: create_critic_collapsible() + CriticFeedbackWidget
  └── app.call_from_thread(conversation_manager.post_message, CriticResultReceived(...))
  ↓
ConversationManager._on_critic_result_received()      [tui/core/conversation_manager.py:215-223]
  → RefinementController.handle_critic_result()
  ↓
RefinementController.handle_critic_result()           [tui/core/refinement_controller.py:66]
  ├── Guard: return if enable_iterative_refinement is False
  ├── Guard: return if current_iteration >= max_refinement_iterations
  ├── should_refine, issues = should_trigger_refinement(critic_result, thresholds)
  ├── Guard: return if not should_refine
  ├── state.set_refinement_iteration(current + 1)     ← INCREMENT
  └── post_message(SendRefinementMessage(refinement_prompt))
  ↓
ConversationManager._on_send_refinement_message()     [tui/core/conversation_manager.py:205-213]
  → message_controller.handle_refinement_message()    ← does NOT reset counter
  ↓
[Agent responds → CriticResult possibly attached → cycle repeats]
```

**Counter reset on new user message:**
```
User submits → SendMessage → ConversationManager._on_send_message()
  → refinement_controller.reset_iteration()            ← RESET to 0
  → visualizer.render_user_message() → _dismiss_pending_feedback_widgets()
```

### 4.3 Refinement Counter — Three Locations

| Operation | Location | Method |
|---|---|---|
| **Lives** | `ConversationContainer.refinement_iteration` (`tui/core/state.py:136`) | Reactive `var[int]`, default `0` |
| **Reset → 0** | `RefinementController.reset_iteration()` (`tui/core/refinement_controller.py:111`) | Called on every new `SendMessage` |
| **Reset → 0** | `ConversationContainer.reset_conversation_state()` (`tui/core/state.py:422`) | Called on conversation switch/new |
| **Increment** | `RefinementController.handle_critic_result()` (`tui/core/refinement_controller.py:97-98`) | After all guards pass |

### 4.4 Two Thresholds

| Threshold | Default | Field | Meaning |
|---|---|---|---|
| `critic_threshold` | 0.6 | `CriticSettings.critic_threshold` | Overall success score. Below this → refinement triggers. |
| `issue_threshold` | 0.75 | `CriticSettings.issue_threshold` | Per-issue probability. At or above this → that issue triggers refinement. |

**Evaluation in `should_trigger_refinement()` (`tui/utils/critic/refinement.py:130`):**

```python
# Trigger condition is an OR:
if critic_result.score < threshold:        # Overall score too low
    return True, high_prob_issues
if high_prob_issues:                       # Specific high-probability issues found
    return True, high_prob_issues
return False, []
```

Only `"agent_behavioral_issues"` from `critic_result.metadata["categorized_features"]` are evaluated for the issue threshold. Infrastructure issues are displayed but don't trigger refinement. Issues are sorted by probability descending before building the refinement prompt.

### 4.5 `CriticSettings`

```python
# stores/cli_settings.py
class CriticSettings(BaseModel):
    enable_critic: bool = True
    enable_iterative_refinement: bool = False
    critic_threshold: float = 0.6
    issue_threshold: float = 0.75
    max_refinement_iterations: int = 3
```

Nested in `CliSettings.critic`, persisted to `cli_config.json`. Field validators enforce threshold ranges (0.0–1.0) and max-iteration bounds (1–10).

---

## 5. Threading Model

### 5.1 TUI Threading

The TUI runs on Textual's event loop (main thread). All SDK blocking calls are offloaded:

**`run_in_executor` (asyncio thread-pool) — two sites:**
```python
# tui/core/conversation_runner.py:125-127  (process_message_async)
await asyncio.get_event_loop().run_in_executor(
    None, self._run_conversation_sync, message, headless
)

# tui/core/conversation_runner.py:203-204  (resume_after_confirmation)
await asyncio.get_event_loop().run_in_executor(
    None, self._execute_conversation, decision
)
```

**`asyncio.to_thread` (for pause/condense):**
```python
# tui/core/conversation_runner.py:220, 245
await asyncio.to_thread(self.conversation.pause)
await asyncio.to_thread(self.conversation.condense)
```

**Textual `run_worker` has two modes:**
- Async worker (default) for coroutine jobs like `process_message_async` and `resume_after_confirmation`.
- Thread worker (`thread=True`) for conversation switching:
```python
# tui/core/conversation_switch_controller.py:83-90
self._run_worker(
    worker,
    name="switch_conversation",
    group="switch_conversation",
    exclusive=True,
    thread=True,
    exit_on_error=False,
)
```

### 5.2 The `_schedule_update` Gate

`ConversationContainer._schedule_update()` (`tui/core/state.py:317-333`) is the central thread-safety mechanism for reactive state:

```python
def _schedule_update(self, attr: str, value: Any) -> None:
    def do_update():
        setattr(self, attr, value)
    if threading.current_thread() is threading.main_thread():
        do_update()                          # Direct mutation
    else:
        self.app.call_from_thread(do_update) # Schedule on main thread
```

**Every public setter** (`set_running`, `set_metrics`, `set_conversation_id`, etc.) routes through this gate. Direct `setattr` on reactive vars from a worker thread (bypassing `set_*` methods) is a bug.

Note: `reset_conversation_state()` uses direct assignment but is safe because it is always invoked on the main thread (switch path via `call_from_thread`; new-conversation path via Textual message handler).

`ConversationVisualizer` also has a parallel UI-thread helper (`_run_on_main_thread`) for widget-mounting work initiated by event callbacks.

### 5.3 ACP Threading

Pure asyncio — no Textual, no `_schedule_update`. The key pattern:

```python
# acp_impl/runner.py:54
await asyncio.to_thread(conversation.run)    # SDK blocking call in thread
```

Events from the SDK thread use `asyncio.run_coroutine_threadsafe` to bridge back (see [Section 1.5](#15-thread-bridging-pattern)).

ACP task lifecycle is tracked per session (`_running_tasks`); cancellation pauses the conversation, awaits task completion with timeout, then falls back to `task.cancel()` when needed.

### 5.4 Comparison

| Aspect | TUI | ACP |
|---|---|---|
| SDK `run()` | `run_in_executor` (via async workers) / thread worker for switch | `asyncio.to_thread` |
| Thread-safe UI updates | `_schedule_update` → `call_from_thread`; plus visualizer `_run_on_main_thread` | N/A (no UI) |
| Event delivery from worker | `post_message` (thread-safe) and `call_from_thread(post_message)` | `run_coroutine_threadsafe` |
| Cancellation | `conversation.pause()` via `to_thread` or switch worker | `conversation.pause()` + await task (then `Task.cancel()` on timeout) |

### 5.5 Thread Safety Rules

| Operation | Safe From | Mechanism |
|---|---|---|
| Update `ConversationContainer` reactive vars | Any thread | `_schedule_update` auto-detects |
| Mount Textual widgets from callbacks | Any thread | Visualizer `_run_on_main_thread` / `call_from_thread` |
| Post Textual messages | Any thread | Textual thread-safe `post_message` |
| SDK `conversation.run()` | Worker thread only | Never call from main thread |
| SDK `conversation.pause()` | Any thread | Thread-safe in SDK |
| Read reactive vars | Any thread (read-only) | No synchronization needed |
| ACP `conn.session_update()` | Main event loop only | Via `run_coroutine_threadsafe` |

---

## 6. Key Code Paths

### 6.1 User Message → Agent Response (TUI)

```
User presses Enter in InputField
  → SingleLineInputWithWrapping.EnterPressed fires
  → InputField._on_enter_pressed()                          [input_field.py:306]
  → InputField._submit_current_content()                    [input_field.py:346]
  → post_message(SendMessage(content))                      [main thread]
  → [bubbles up DOM]
  → ConversationManager._on_send_message()                  [tui/core/conversation_manager.py:194]
  → refinement_controller.reset_iteration()                 [resets counter to 0]
  → UserMessageController.handle_user_message(content)      [tui/core/user_message_controller.py:30]
     ├── Guard: if conversation_id is None → return
     ├── runner = runners.get_or_create(conversation_id)
     ├── runner.visualizer.render_user_message(content)
     ├── state.set_conversation_title(content)
     └── _process_message(runner, content)                  [tui/core/user_message_controller.py:77]
         ├── if runner.is_running:
         │     runner.queue_message(content)                [enqueue into running conversation]
         └── else:
               run_worker(runner.process_message_async())   [schedules worker]
                 → run_in_executor(_run_conversation_sync)  [thread pool]
                   → conversation.send_message(message)     [blocks]
                   → _execute_conversation()
                     → _update_run_status(True)             [→ call_from_thread]
                     → conversation.run()                   [BLOCKS — main agent loop]
                     → [SDK fires event callbacks → visualizer renders in real time]
                     → if WAITING_FOR_CONFIRMATION:
                         _request_confirmation()            [→ ShowConfirmationPanel]
                     → _update_run_status(False)            [→ call_from_thread; in finally]
  → watch_running() triggers                                [main thread]
  → post_message(ConversationFinished())
```

### 6.2 Conversation Switch While Running

```
User clicks history entry for conversation B (A is running)
  → SwitchConversation(B) bubbles to ConversationManager
  → ConversationSwitchController.request_switch(B)          [tui/core/conversation_switch_controller.py:38]
  → state.running == True → set_switch_confirmation_target(B)
  → post_message(RequestSwitchConfirmation(B))              [bubbles to App]
  → App shows SwitchConversationModal
  → User confirms → SwitchConfirmed(B, confirmed=True)
  → ConversationManager._on_switch_confirmed()
  → ConversationSwitchController.handle_switch_confirmed(B, confirmed=True)
  → _perform_switch(B, pause_current=True)                  [tui/core/conversation_switch_controller.py:60]
    → state.start_switching()                               [conversation_id=None, input disables]
    → run_worker(thread=True, group="switch_conversation", exclusive=True):
        → runner_A.conversation.pause()                     [BLOCKS until SDK pauses]
        → call_from_thread(safe_prepare)                    [schedule back to main thread]
    → [main thread] _prepare_switch(B):
        → state.reset_conversation_state()
        → runners.clear_current()
        → runners.get_or_create(B)                          [creates runner, replays history]
          → RunnerFactory.create(B) → ConversationRunner
          → runner_B.replay_historical_events()             [renders B's history to scroll view]
        → state.finish_switching(B)                         [conversation_id=B, input enables]
        → state.set_switch_confirmation_target(None)

Note: if state.running == False, request_switch() skips confirmation and directly calls
_perform_switch(B, pause_current=False).
```

### 6.3 Conversation Resume/Replay

**TUI:** `RunnerRegistry.get_or_create()` calls `runner.replay_historical_events()` → `visualizer.replay_events(events)`. Events are already in memory (SDK loads from `persistence_dir`). Replay is **synchronous on main thread**, skipping side effects (critic, telemetry). For brand-new conversations this is a no-op.

**ACP:** `new_session()` with `is_resuming=True` iterates `conversation.state.events` and `await subscriber(event)` for each — **streaming events individually to the IDE client** via ACP protocol. `load_session()` also iterates all events and replays them on each call.

| Aspect | TUI | ACP |
|---|---|---|
| Trigger | `RunnerRegistry.get_or_create()` | `new_session`/`load_session` |
| Delivery | `visualizer.replay_events()` (batch) | `EventSubscriber(event)` per event (async) |
| Thread | Main thread | Async event loop |
| Side effects | Skipped (replay mode) | Forwarded as-is |
| Idempotency | `_historical_events_replayed` flag | `_active_sessions` avoids re-creating conversation objects; `load_session` still replays history |

### 6.4 ACP Streaming vs Non-Streaming

**Non-streaming:** `sync_callback(event)` → `run_coroutine_threadsafe(subscriber(event))` → `EventSubscriber` sends complete events as they arrive. One ACP update per SDK event.

**Streaming:** Two parallel paths:
1. `on_token(chunk)` → `_schedule_update()` → real-time token delivery (content/reasoning text + incremental tool call args).
2. `sync_callback(event)` → `token_subscriber.unstreamed_event_handler(event)` → updates tool call summaries, handles observations.

Streaming produces many small updates (per-token); non-streaming produces fewer, larger updates (per-event).

Note: ACP `prompt()` creates the run task with `asyncio.create_task(...)` but immediately `await`s it; `PromptResponse(stop_reason="end_turn")` returns only after run completion/pause.

---

## 7. Key Interfaces Reference

### `ConversationStore` Protocol (`conversations/protocols.py`)

```python
class ConversationStore(Protocol):
    def list_conversations(self, limit: int = 100) -> list[ConversationMetadata]: ...
    def get_metadata(self, conversation_id: str) -> ConversationMetadata | None: ...
    def get_event_count(self, conversation_id: str) -> int: ...
    def load_events(self, conversation_id, limit=None, start_from_newest=False) -> Iterator[Event]: ...
    def exists(self, conversation_id: str) -> bool: ...
    def create(self, conversation_id: str | None = None) -> str: ...
```

Structural protocol (duck-typed). Two declared classes: `LocalFileStore` (fully implemented) and `CloudStore` (stub; methods currently raise `NotImplementedError`).

### `ConversationContainer` Reactive Variables (`tui/core/state.py`)

| Variable | Type | Default | Purpose |
|---|---|---|---|
| `running` | `bool` | `False` | Conversation processing state. Drives timer, `ConversationFinished`, UI busy indicators. |
| `conversation_id` | `UUID \| None` | `None` | Active conversation. `None` = switch in progress. Drives InputField disabled state. |
| `conversation_title` | `str \| None` | `None` | First user message text for history panel. |
| `confirmation_policy` | `ConfirmationPolicyBase` | `AlwaysConfirm()` | Current policy. Preserved across conversation switches. |
| `pending_action_count` | `int` | `0` | Pending confirmations. `>0` shows InlineConfirmationPanel, disables input. |
| `switch_confirmation_target` | `UUID \| None` | `None` | Conversation being switched to, pending confirmation. |
| `elapsed_seconds` | `int` | `0` | Timer for working status line. |
| `metrics` | `Metrics \| None` | `None` | LLM usage metrics for info status line. |
| `loaded_resources` | `LoadedResourcesInfo \| None` | `None` | Skills, hooks, MCP servers for splash content. |
| `critic_settings` | `CriticSettings` | `CriticSettings()` | Critic config for working status line + refinement. |
| `refinement_iteration` | `int` | `0` | Current refinement pass within a turn. |

### `BaseOpenHandsACPAgent` Abstract Contract (`acp_impl/agent/base_agent.py`)

See [Section 1.2](#12-abstract-contract-baseopenhandsacpagent).

### `AgentStore.load_or_create()` Assembly Pipeline (`stores/agent_store.py`)

See [Section 2.4](#24-complete-load-chain).

### Key Textual Messages (`tui/messages.py`, `tui/core/events.py`, `tui/core/state.py`, `tui/core/conversation_manager.py`)

| Message | Carries | Flow |
|---|---|---|
| `SendMessage` | `content: str` | InputField → ConversationManager |
| `SendRefinementMessage` | `content: str` | RefinementController → ConversationManager |
| `ShowConfirmationPanel` | `pending_actions: list[ActionEvent]` | ConversationRunner → ConversationManager |
| `ConfirmationDecision` | `decision: UserConfirmation` | InlineConfirmationPanel → ConversationManager |
| `RequestSwitchConfirmation` | `target_id: UUID` | SwitchController → App |
| `SwitchConfirmed` | `target_id: UUID, confirmed: bool` | App → ConversationManager |
| `CriticResultReceived` | `critic_result: CriticResult` | Visualizer → ConversationManager |
| `ConversationFinished` | — | ConversationContainer.watch_running → App |
| `SwitchConversation` | `conversation_id: UUID` | HistorySidePanel → ConversationManager |
| `CreateConversation` | — | InputAreaContainer → ConversationManager |
| `PauseConversation` | — | OpenHandsApp (Esc key binding) → ConversationManager |
| `CondenseConversation` | — | InputAreaContainer (`/condense`) → ConversationManager |
| `SetConfirmationPolicy` | `policy: ConfirmationPolicyBase` | InputAreaContainer (`/confirm` + modal callback) → ConversationManager |

**Notes:**
- `SlashCommandSubmitted` is posted by `InputField` and handled by `InputAreaContainer` before downstream messages like `CreateConversation`, `CondenseConversation`, or `SetConfirmationPolicy` are emitted.
- `ConfirmationRequired` is defined/exported but not used in active flow; `ShowConfirmationPanel` is the effective confirmation-panel message.
