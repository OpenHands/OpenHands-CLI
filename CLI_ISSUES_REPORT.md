# CLI Issues Report

Issues sourced from `CLI_ISSUES_ROUGH.md`, assessed for legitimacy and cross-referenced against open GitHub issues.

**Legend:**
- 🔴 Not tracked — new issue needed
- 🟡 Partially tracked — related issue exists, but doesn't fully cover this case
- 🟢 Already tracked — existing open issue covers this
- ⚪ Stale/resolved — likely fixed or no longer valid

---

## 1. Ask Permission Dialog Should Allow Chat Message
**Status:** 🔴 Not tracked

The `InlineConfirmationPanel` only offers Yes / No / Always / Auto LOW/MED options.
There is no way to send a message back to the agent from the confirmation dialog (e.g., "Do it, but use a different approach" or "Add a test first").

**Relevant code:** `openhands_cli/tui/panels/confirmation_panel.py` — `InlineConfirmationPanel.OPTIONS`

**Fix direction:** Add a "Send message" option that dismisses the confirmation panel and opens the input field (or an inline text input) pre-focused, pausing the pending action until the message is handled.

---

## 2. Unicode Error on AGENTS.md
**Status:** 🔴 Not tracked

Crash on startup when `AGENTS.md` (or any skill file) contains non-UTF-8 bytes (e.g., binary content, Latin-1/Windows-1252 text). Full traceback:

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd1 in position 4450: invalid continuation byte
```

**Root cause:** `openhands/sdk/context/skills/skill.py`, `Skill.load()` opens the file with `f.read()` and no `errors` parameter — crashes on any non-UTF-8 byte.

**Fix direction:** The fix belongs in the SDK (`Skill.load`): open with `encoding="utf-8", errors="replace"` (or `"ignore"`). As a CLI-side workaround, wrap the `load_project_skills` call in a try-except that logs a warning and continues rather than crashing on startup.

---

## 3. LLMBadRequestError (Tool-Use / Tool-Result Mismatch)
**Status:** 🟡 Partially tracked as [#533](https://github.com/OpenHands/OpenHands-CLI/issues/533)

Issue #533 covers a `BadRequestError` where LiteLLM message history has tool-call entries with missing `content` fields (OpenRouter variant). The rough-notes error is a distinct Anthropic-flavored variant: `tool_use` blocks exist without the required `tool_result` blocks immediately after:

```
AnthropicException: messages.12: `tool_use` ids were found without `tool_result` blocks
immediately after: toulu_01CQB2o5kUiR4wv...
```

Both point to the same root cause: the conversation history is getting into an inconsistent state — likely during context condensation or after an error that drops half a tool-call/result pair.

**Fix direction:** In the agent-sdk conversation/condensation logic, validate that every `tool_use` block has a matching `tool_result` before sending to the LLM. Strip or repair orphaned pairs before the API call rather than crashing.

---

## 4. Console Logs Appear Interspersed With the TUI
**Status:** 🔴 Not tracked

During a TUI session (non-headless), `Console().print()` calls in `openhands_cli/setup.py` write directly to stdout, breaking the Textual display:

```python
# openhands_cli/setup.py  ~line 119
console.print("Initializing agent...", style="white")
console.print("✓ Hooks loaded", style="green")
console.print(f"✓ Agent initialized with model: {agent.llm.model}", style="green")
```

`setup_conversation()` is called from `ConversationRunner.__init__` the first time a message is sent, so these prints fire while the TUI is live.

**Fix direction:** Remove or guard these prints. In TUI mode pass a flag/callback so startup progress surfaces through a Textual `notify()` call instead.

---

## 5. Model Selection Is Hard to Find (No Slash Command)
**Status:** 🟢 Already tracked as [#451](https://github.com/OpenHands/OpenHands-CLI/issues/451)

Users must open the Command Palette to find "Open Settings" to change the model. There is no `/config` or `/model` slash command.

See [#451 — Add `/config` to configure model, provider, and settings](https://github.com/OpenHands/OpenHands-CLI/issues/451).

---

## 6. Auto-Copy Is Inconsistent
**Status:** 🟡 Partially tracked — [#296](https://github.com/OpenHands/OpenHands-CLI/issues/296) (copy button hidden until hover), [#224](https://github.com/OpenHands/OpenHands-CLI/issues/224) (copy-paste not working)

Auto-copy is triggered in `on_mouse_up` via `screen.get_selected_text()`. This is unreliable in environments where the terminal handles mouse events itself (e.g., tmux, SSH, some macOS Terminal configurations), meaning text selection may silently fail, fire on the wrong text, or not fire at all.

**Fix direction:** Improve detection of when `get_selected_text()` returns a meaningful selection. Consider surfacing a failure state to the user rather than silently doing nothing, and document known environment limitations (e.g., tmux requires `set -g mouse on` and may need OSC 52).

---

## 7. Permission Selector Misfires on Click
**Status:** 🔴 Not tracked

The `InlineConfirmationPanel` uses a `ListView` whose `on_list_view_selected` fires immediately on any click within the list area. It is easy to accidentally accept, reject, or change the confirmation policy by clicking in the wrong area of the screen, especially on a high-DPI or small terminal.

**Relevant code:** `openhands_cli/tui/panels/confirmation_panel.py` — `on_list_view_selected`

**Fix direction:** Either require a double-click / Enter key to commit a selection, or add a brief debounce/confirmation step for destructive choices (Always, Yes) so a single accidental click does not immediately trigger the action.

---

## 8. Resume Doesn't Work With Headless Mode
**Status:** 🔴 Not tracked

`openhands --headless` requires `--task` or `--file` (enforced in `entrypoint.py`). Combining `--headless --resume <id> --task "..."` should work in theory (both are wired through `textual_main`), but is not validated and likely has edge-case failures. One known gap: there is no way to resume a headless session *without* providing a new task, even if you just want to continue where the agent left off.

**Fix direction:** Validate that `--headless --resume` with a task actually continues the conversation from the stored state. Consider relaxing the `--task` requirement when `--resume` is provided (the resumed context itself is the prompt).

---

## 9. Headless Mode: No Human-Readable Log During Session
**Status:** 🟡 Partially addressed — [#317](https://github.com/OpenHands/OpenHands-CLI/issues/317) was closed (spinners removed, now prints "Agent is working" / "Agent finished")

Currently headless offers two extremes:
- **Silent** (no `--json`): only start/end status lines
- **Full JSON** (`--json`): every SDK event as a JSON blob, plus embedded spinner characters that break parsing

There is no intermediate mode: a human-readable, real-time conversation log (the text equivalent of what the TUI shows) and no concise one-line-per-event summary format.

**Fix direction:** Add a `--log-format text|oneline|json` option (or `--verbose` flag) that, in headless mode, prints events as readable text (agent messages, tool call summaries, etc.) without the full JSON dump.

---

## 10. Conversation ID Not Shown During Headless Session
**Status:** 🔴 Not tracked

In `entrypoint.py`, `conversation_id` is printed **after** `textual_main()` returns:

```python
# entrypoint.py ~line 232
console.print(f"Conversation ID: {conversation_id.hex}", ...)
```

For a long-running headless task there is no way to find the conversation ID while it is running — which makes it impossible to view the log in progress (`openhands view --id <id>`) or recover the ID if the process is killed.

**Fix direction:** Print the conversation ID at the **start** of a headless session, before the agent runs.

---

## 11. Headless Summary Should Include Cost
**Status:** 🔴 Not tracked

`_print_conversation_summary()` in `textual_app.py` shows:
- Number of agent messages
- Last agent message text

It does not show total token usage or accumulated cost, even though `ConversationContainer.metrics` (a `Metrics` object) tracks this data in real time.

**Relevant code:** `openhands_cli/tui/textual_app.py` — `_print_conversation_summary()`; `openhands_cli/tui/core/state.py` — `ConversationContainer.metrics`

**Fix direction:** After the run completes, read `self.conversation_state.metrics` and include cost/token counts in the summary output.

---

## 12. System Prompt Displays in Full by Default (Very Long)
**Status:** ⚪ Mostly stale / partially fixed

`default_cells_expanded` defaults to `False` in `CliSettings`, so collapsibles — including the system-prompt collapsible — are collapsed by default. The reported issue is likely only observed when a user has set `default_cells_expanded = True`, in which case the system prompt (which can be thousands of tokens) expands fully.

**Remaining concern:** When `default_cells_expanded = True`, the system-prompt collapsible arguably should still be collapsed, because it is rarely useful to read and is very long compared to tool outputs or messages.

**Fix direction:** Force the system-prompt collapsible to always start collapsed (pass `collapsed=True` explicitly in `_create_system_prompt_collapsible`), independent of the global `default_cells_expanded` setting.

---

## 13. Deprecation Warnings From opentelemetry
**Status:** 🔴 Not tracked (unrelated [#72](https://github.com/OpenHands/OpenHands-CLI/issues/72) covers a different deprecation warning)

```
opentelemetry/_events/__init__.py:201: DeprecationWarning: You should use `ProxyLoggerProvider`...
```

These warnings fire at **import time** (module-level `ProxyEventLoggerProvider()` instantiation in opentelemetry). In `entrypoint.py`, `warnings.filterwarnings("ignore")` is called **after** the openhands_cli imports that transitively pull in opentelemetry, so the filter does not suppress them.

**Fix direction:** Move `warnings.filterwarnings("ignore")` (or a targeted `warnings.filterwarnings("ignore", category=DeprecationWarning, module="opentelemetry")`) to before the openhands_cli imports in `entrypoint.py`.

---

## 14. Context Error: "Failed to detach context"
**Status:** 🔴 Not tracked

```
ERROR  Failed to detach context
ValueError: <Token var=... at 0x...> was created in a different Context
  opentelemetry/context/contextvars_context.py:53 in detach
```

This occurs because the conversation runner executes in a background thread (`asyncio.to_thread` / `run_in_executor`). opentelemetry's `ContextVar`-based context tokens are not valid across thread boundaries — a token created in the main thread cannot be `reset()` from a worker thread (and vice versa).

The error is caught and logged (not fatal), but it is noisy and may mask real issues.

**Fix direction:** Disable opentelemetry tracing in CLI mode (it is not needed for end-user CLI use), or configure the opentelemetry context propagator to be a no-op. This would eliminate the error entirely.

---

## Summary Table

| # | Issue | Status | Tracked |
|---|-------|--------|---------|
| 1 | Permission dialog should allow chat message | 🔴 New issue | — |
| 2 | Unicode error on AGENTS.md | 🔴 New issue | — |
| 3 | LLMBadRequestError (tool_use/tool_result mismatch) | 🟡 Partial | [#533](https://github.com/OpenHands/OpenHands-CLI/issues/533) |
| 4 | Console logs interspersed with TUI | 🔴 New issue | — |
| 5 | Model selection hard to find (no slash command) | 🟢 Tracked | [#451](https://github.com/OpenHands/OpenHands-CLI/issues/451) |
| 6 | Auto-copy inconsistent | 🟡 Partial | [#296](https://github.com/OpenHands/OpenHands-CLI/issues/296), [#224](https://github.com/OpenHands/OpenHands-CLI/issues/224) |
| 7 | Permission selector misfires on click | 🔴 New issue | — |
| 8 | Resume doesn't work with headless mode | 🔴 New issue | — |
| 9 | Headless: no human-readable log during session | 🟡 Partial | [#317](https://github.com/OpenHands/OpenHands-CLI/issues/317) closed |
| 10 | Conversation ID not shown during headless session | 🔴 New issue | — |
| 11 | Headless summary should include cost | 🔴 New issue | — |
| 12 | System prompt displays in full by default | ⚪ Mostly stale | — |
| 13 | Deprecation warnings from opentelemetry | 🔴 New issue | — |
| 14 | Context error: "Failed to detach context" | 🔴 New issue | — |
