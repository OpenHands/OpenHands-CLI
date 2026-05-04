# Proposal: Claude Code plugin powered by OpenHands headless mode

## Summary

This document proposes a Claude Code plugin that can delegate work to OpenHands from inside a Claude Code session, following the same broad pattern used by `openai/codex-plugin-cc`:

- Claude Code command or subagent
- thin local companion runtime
- background job management and persisted results
- a delegated engine running outside the Claude Code process

For OpenHands, the recommended engine for v1 is **OpenHands CLI headless mode**, not a custom SDK runtime.

That gives us a fast path to an MVP while reusing the same agent, tool, persistence, and settings model that already ships in the CLI.

## Goals

- Let Claude Code users delegate bounded tasks to OpenHands without leaving Claude Code.
- Reuse existing OpenHands CLI and SDK capabilities rather than inventing a new runtime first.
- Support both foreground and background execution.
- Preserve repository context by running OpenHands against the current working directory.
- Make it possible to resume work, inspect results, and cancel long-running tasks.

## Non-goals

- Embedding the full OpenHands TUI inside Claude Code.
- Replacing ACP or the existing IDE integration path.
- Designing a brand new agent runtime before validating the workflow.
- Solving every multi-agent orchestration problem in the first iteration.

## Why headless CLI first

The current CLI already provides most of what a Claude Code plugin needs:

- `openhands --headless -t "..."` for one-shot delegated work
- `--resume` and `--last` for conversation continuation
- `OPENHANDS_WORK_DIR` support to bind execution to the current repository
- the default CLI agent powered by the OpenHands Software Agent SDK
- existing persistence for conversations and settings
- optional JSON event output

The Codex Claude Code plugin is a thin wrapper around a companion runtime. We should mirror that structure and keep the Claude Code layer small.

Compared with building directly on the SDK, the CLI path gives us:

- less runtime setup work
- fewer configuration questions in v1
- behavior that already matches how OpenHands users run the product today
- a natural upgrade path to an SDK-backed runtime later if we outgrow the CLI shell boundary

## Alternatives considered

### 1. Direct SDK runtime inside the plugin companion

This is attractive long term because it gives tighter control over:

- event streaming
- persistence and conversation identity
- confirmation policy
- structured outputs
- custom toolsets and custom agents

However, it also means the plugin companion would own:

- Python environment setup
- agent construction
- model and secret configuration
- persistence conventions
- compatibility with CLI expectations

This is likely the right direction only after the workflow proves itself.

### 2. ACP as the integration boundary

ACP is valuable for IDE integrations, but it does not appear to be the right primary abstraction for a Claude Code plugin. Claude Code plugins are better matched by the Codex pattern of shelling out to a local companion runtime.

ACP should remain available for editor integrations, but it is not the recommended starting point for this feature.

## Recommended architecture

```text
Claude Code plugin
  ├─ slash commands / subagent definitions
  └─ openhands companion runtime
       ├─ validates OpenHands installation and configuration
       ├─ launches foreground or background jobs
       ├─ stores plugin job metadata
       ├─ maps plugin jobs to OpenHands conversation IDs
       └─ invokes OpenHands CLI headless mode

OpenHands CLI
  └─ OpenHands SDK agent + tools + persistence
```

## User experience

### Proposed commands

Initial command set:

- `/openhands:setup`
- `/openhands:task`
- `/openhands:resume`
- `/openhands:status`
- `/openhands:result`
- `/openhands:cancel`

Optional later additions:

- `/openhands:review` for read-only review-focused runs
- `/openhands:plan` for planning/spec generation only
- `/openhands:handoff` for structured Claude ⇄ OpenHands delegation

### Example flows

#### Simple foreground task

```text
/openhands:task fix the flaky login test with the smallest safe patch
```

The plugin companion would run something like:

```bash
OPENHANDS_WORK_DIR="$PWD" openhands --headless --override-with-envs -t "fix the flaky login test with the smallest safe patch"
```

#### Background task

```text
/openhands:task --background investigate why this branch broke on Linux
```

The plugin companion would:

1. start the job in the background
2. capture stdout and stderr
3. persist a plugin job record
4. store the OpenHands conversation ID when available
5. return a compact status message to Claude Code

#### Resume previous work

```text
/openhands:resume continue from the last OpenHands run and apply the safest fix
```

The plugin companion would map this to the most recent stored conversation ID for the repository and run `openhands --headless --resume <id> ...`.

## Job model

The plugin should maintain its own lightweight job registry separate from OpenHands conversation persistence.

Suggested fields:

- `job_id`
- `repo_root`
- `created_at`
- `updated_at`
- `status` (`running`, `succeeded`, `failed`, `cancelled`)
- `pid` for background execution
- `conversation_id` for OpenHands resume support
- `task_text`
- `command`
- `stdout_path`
- `stderr_path`
- `result_path`

This mirrors the Codex plugin approach and gives the Claude Code side stable commands for status, result, and cancellation even if the OpenHands process exits.

## CLI gaps and suggested enhancements

The current CLI is already close, but a plugin-quality integration would benefit from a few targeted improvements.

### 1. Cleaner machine-readable output

Today `--json` is useful, but plugin integration would be easier with one of:

- strict JSONL event output without extra markers, or
- a dedicated machine-readable summary emitted at the end of headless runs

Suggested addition:

- `openhands --headless --jsonl`

or

- `openhands --headless --result-json`

### 2. Explicit conversation ID reporting

The plugin needs a stable way to discover the new or resumed conversation ID.

Suggested addition:

- emit `conversation_id` in machine-readable form at startup and completion

### 3. Stable headless exit semantics

We should document and test exit codes for:

- success
- agent failure
- configuration failure
- interrupted or cancelled execution

### 4. Optional repo-scoped state helpers

Not required for v1, but convenient later:

- a dedicated command to print the latest conversation ID for the current work dir
- an easier way to resume the last conversation for a given repo in headless automation

## Configuration model

The plugin companion should support two setup paths:

### Option A: existing OpenHands CLI config

If the user has already configured `openhands`, `/openhands:setup` should detect that and report ready status.

### Option B: environment-driven setup

For automation-friendly usage, the companion should support passing through:

- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_BASE_URL`

with `--override-with-envs`.

This should be the default path for CI-like or plugin-managed runs.

## Security model

Important behavior to acknowledge up front:

- CLI headless mode is intended for automation and does not provide the same interactive confirmation loop as the TUI.
- Plugin commands should therefore be explicit about whether a run is read-only or write-capable.
- The initial command set should bias toward clear semantics rather than magical delegation.

Recommended v1 guardrails:

- separate read-only and write-capable command variants where possible
- document that `/openhands:task` may modify the repository
- keep `/openhands:review` or `/openhands:plan` read-only when introduced

## Where the code should live

The Claude Code plugin itself likely belongs in a separate repository, similar to `openai/codex-plugin-cc`.

This repository would own the CLI improvements that make that plugin reliable:

- better headless machine output
- any small resume or reporting helpers
- tests covering plugin-oriented headless behavior

## Implementation plan

### Phase 0: design alignment

- agree that the v1 runtime is OpenHands CLI headless mode
- agree that the Claude Code plugin lives in a separate repo
- confirm the minimum command set and security expectations

### Phase 1: make CLI headless plugin-friendly

In `OpenHands-CLI`:

1. add a stricter machine-readable headless output mode
2. emit conversation IDs in machine-readable form
3. document headless exit codes and behavior
4. add tests for plugin-oriented headless flows

Suggested test coverage:

- `--headless` + machine-readable output
- success path with reported conversation ID
- resume path preserving conversation identity
- configuration failure path
- interrupted run or cancellation path

### Phase 2: build plugin companion runtime

In a new plugin repo:

1. implement setup checks for `openhands` availability
2. implement foreground execution
3. implement background job tracking
4. implement status, result, and cancel commands
5. map plugin jobs to OpenHands conversation IDs

### Phase 3: build the Claude Code plugin UX

In the plugin repo:

1. define plugin manifest and marketplace metadata
2. add slash commands
3. add a dedicated `openhands-rescue`-style subagent if needed
4. tune command prompts for foreground vs background recommendations
5. document installation and setup

### Phase 4: evaluate SDK-backed runtime

After validating usage:

1. decide whether CLI subprocess boundaries are sufficient
2. if not, replace the companion's execution layer with a direct SDK runtime
3. preserve the same Claude Code command surface so migration is transparent

## Testing strategy

### In this repository

- unit tests for new headless output helpers
- integration tests around conversation ID reporting and resume behavior
- command reference and headless docs updates when flags or output modes change

### In the plugin repository

- runtime tests with fake OpenHands subprocesses
- job state transition tests
- background process lifecycle tests
- slash command behavior tests

## Open questions

- Should the first release expose a single general-purpose `/openhands:task` command, or separate read-only and write-capable entry points immediately?
- Should the plugin default to `--override-with-envs`, or prefer existing CLI configuration when both are available?
- Do we want strict JSONL, a single final JSON summary, or both?
- Is a separate `/openhands:resume` command clearer than implicit repo-local resume behavior?
- Should the plugin companion store state per repository, per workspace root, or globally with repo scoping?

## Recommendation

Proceed with a **CLI-headless-backed Claude Code plugin** as the first implementation.

That path is the fastest way to validate the workflow, keeps the Claude Code integration thin, and leverages the OpenHands CLI and SDK exactly where they are already strongest.

If the integration proves valuable and we need tighter event control later, we can move the companion runtime to the SDK without changing the user-facing Claude Code commands.
