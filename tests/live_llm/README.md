# Live LLM Integration Tests

End-to-end tests that run the **real CLI** against a **real LLM provider** in
`--headless` mode.  They are intentionally expensive and opt-in.

## Quick start

```bash
# Run locally (needs LLM credentials)
LLM_API_KEY="sk-..." \
LLM_MODEL="anthropic/claude-sonnet-4-5-20250929" \
  uv run pytest tests/live_llm/ --run-live-llm -v

# With a LiteLLM proxy
LLM_API_KEY="..." \
LLM_MODEL="openhands/claude-haiku-4-5-20251001" \
LLM_BASE_URL="https://llm-proxy.app.all-hands.dev" \
  uv run pytest tests/live_llm/ --run-live-llm -v
```

## How it works

Each test:

1. Calls the CLI via `python -m openhands_cli.entrypoint --headless --task "..." --override-with-envs --always-approve`
2. Captures `stdout` / `stderr`
3. Asserts **relaxed behavioural keywords** (not exact output)

Tests are skipped automatically when `--run-live-llm` is not passed, so
`make test` is unaffected.

## CI trigger

In CI, these tests are triggered by adding the **`run-live-llm`** label to a
pull request (see `.github/workflows/live-llm-tests.yml`).  Results are
posted as a PR comment.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | ✅ | API key for the LLM provider |
| `LLM_MODEL` | ✅ | Model identifier (e.g. `anthropic/claude-sonnet-4-5-20250929`) |
| `LLM_BASE_URL` | ❌ | Custom base URL (e.g. a LiteLLM proxy) |
| `LIVE_LLM_TIMEOUT` | ❌ | Per-test timeout in seconds (default: `300`) |

## Test design

The three tests are chosen to maximise component coverage with minimal LLM calls:

| Test | What it validates |
|---|---|
| `test_echo_command` | LLM connectivity → tool-call → terminal execution → observation → summary |
| `test_file_create_and_read` | Multi-step planning, file I/O, observation correctness |
| `test_python_code_gen_and_run` | Code generation, file creation, Python execution, numeric output |

## Adding new tests

1. Add a new test method/class in `test_live_llm.py`
2. Use the `run_cli` fixture: `result = run_cli("your prompt")`
3. Assert on `result.output` with relaxed keyword checks
4. Keep prompts short and deterministic in expected behaviour
