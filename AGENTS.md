# Repository Guidelines

## Repository Purpose
OpenHands CLI is a standalone terminal interface (Textual TUI) for interacting with the OpenHands agent.

This repo contains the current CLI UX, including the Textual TUI and a browser-served view via `openhands web`.


### References
- Agent-sdk example: https://github.com/All-Hands-AI/agent-sdk/blob/main/examples/hello_world.py
- If you need to compare with upstream OpenHands code, use `$GITHUB_TOKEN` for access.

## Project Structure & Module Organization
- `openhands_cli/`: Core CLI/TUI code (`openhands_cli/entrypoint.py`, `openhands_cli/tui/`, `openhands_cli/auth/`, `openhands_cli/mcp/`, `openhands_cli/cloud/`, `openhands_cli/user_actions/`, `openhands_cli/conversations/`, `openhands_cli/theme.py`, helpers in `openhands_cli/utils.py`). Keep new modules snake_case and colocate tests.
- `tests/`: Pytest suite covering units, integration, and snapshot tests; mirrors source layout. `e2e_tests/`: end-to-end ACP/UI flows.
- `scripts/acp/`: JSON-RPC and debug helpers for ACP development; `hooks/`: PyInstaller/runtime hooks.
- Tooling & packaging: `Makefile` for common tasks, `build.sh`/`build.py` for PyInstaller artifacts, `openhands-cli.spec` for the frozen binary, `uv.lock` for resolved deps.
- `.openhands/skills/`: agent guidance for this repo.

## Setup, Build, and Development Commands
- install dependencies: `make install`
- install dev dependencies: `make install-dev`
- install pre-commit hooks: `uv run pre-commit install` (included in `make build`)
- build (sync + install hooks): `make build`
- lint (all pre-commit hooks): `make lint`
- format: `make format`
- run the Textual TUI (interactive; prefer running inside tmux so you can detach with `Ctrl+b d`): `make run` (or `uv run openhands`)
- run the Textual TUI (automation-friendly; use for agent-driven runs): `uv run openhands --exit-without-confirmation` (quit with `Ctrl+Q`; `Ctrl+C` does not work once the TUI is running)

- run the browser-served web app (Textual `textual-serve`): `openhands web`
- run the Docker-based OpenHands GUI server: `openhands serve`
- run the ACP entrypoint: `uv run openhands-acp`
- run tests: `make test` (for faster runs: `uv run pytest -m "not integration"`; end-to-end: `uv run pytest e2e_tests`)
- build PyInstaller binaries: `./build.sh --install-pyinstaller`

## Development Guidelines

### Linting Requirements
**Always run lint before committing changes.** Use `make lint` to run all pre-commit hooks on all files.

### Typing Requirements
Prefer modern typing syntax (`X | None` over `Optional[X]`) in new code.

### Documentation Guidelines
- Don’t add new root-level `.md` files or “summary updates” to `README.md` unless explicitly requested (use this `AGENTS.md` for repo guidance).

## Coding Style & Naming Conventions
- Python 3.12, ruff formatting (88-char line limit, double quotes).
- Ruff enforced rules: pycodestyle, pyflakes, isort, pyupgrade, unused-arg checks (tests allow fixture-style args), and guards against mutable defaults.
- Keep modules/dirs snake_case; classes in CapWords; user-facing commands/flags kebab-case as in existing entrypoints.
- Type checking via `pyright` (`uv run pyright`); prefer type hints on new functions and public interfaces.

## Testing Guidelines
- Pytest discovery: files `test_*.py`, classes `Test*`, functions `test_*`. Use `@pytest.mark.integration` for costly flows.
- Match test locations to implementation (`tests/` mirrors `openhands_cli/`); add fixtures in `tests/conftest.py` when shared.
- Run `make test` before PRs.

## Snapshot Testing with pytest-textual-snapshot
The CLI uses [pytest-textual-snapshot](https://github.com/Textualize/pytest-textual-snapshot) for visual regression testing of Textual UI components. Snapshots are SVG screenshots that capture the exact visual state of the application.

### Running Snapshot Tests

```bash
# Run all snapshot tests
uv run pytest tests/snapshots/ -v

# Update snapshots when intentional UI changes are made
uv run pytest tests/snapshots/ --snapshot-update
```

### Snapshot Test Location
- **Test files**: `tests/snapshots/test_app_snapshots.py`, `tests/snapshots/test_visualizer_snapshots.py`
- **Generated snapshots**: `tests/snapshots/__snapshots__/test_app_snapshots/*.svg`, `tests/snapshots/__snapshots__/test_visualizer_snapshots/*.svg`

### Writing Snapshot Tests
Snapshot tests must be **synchronous** (not async). The `snap_compare` fixture handles async internally:

```python
from textual.app import App, ComposeResult
from textual.widgets import Static, Footer


def test_my_widget(snap_compare):
    """Snapshot test for my widget."""

    class MyTestApp(App):
        def compose(self) -> ComposeResult:
            yield Static("Content")
            yield Footer()

    assert snap_compare(MyTestApp(), terminal_size=(80, 24))
```

#### Using `run_before` for Setup
To interact with the app before taking a screenshot:

```python
def test_with_interaction(snap_compare):
    class MyApp(App):
        def compose(self) -> ComposeResult:
            yield InputField(id="input")

    async def setup(pilot):
        input_field = pilot.app.query_one(InputField)
        input_field.input_widget.value = "Hello!"
        await pilot.pause()

    assert snap_compare(MyApp(), terminal_size=(80, 24), run_before=setup)
```

#### Using `press` for Key Simulation

```python
def test_with_focus(snap_compare):
    assert snap_compare(
        MyApp(),
        terminal_size=(80, 24),
        press=["tab", "tab"],  # Press tab twice to move focus
    )
```

### Viewing Snapshots Visually
To view the generated SVG snapshots in a browser:

1. **Start a local HTTP server** in the snapshots directory:
   ```bash
   cd tests/snapshots/__snapshots__/test_app_snapshots
   python -m http.server 12000
   ```

2. **Open in browser** using the work host URL:
   ```
   https://work-1-<id>.prod-runtime.all-hands.dev/<snapshot-name>.svg
   ```

   Example snapshot names:
   - `TestExitModalSnapshots.test_exit_modal_initial_state.svg`
   - `TestVisualizerSnapshots.test_multiple_actions_alignment.svg`

3. **Stop the server** when done:
   ```bash
   pkill -f "python -m http.server 12000"
   ```


### Snapshot Best Practices
- Mock external dependencies so snapshots are deterministic.
- Always pass a fixed `terminal_size=(width, height)`.
- Commit SVG snapshots.
- Review snapshot diffs carefully.


## Commit & Pull Request Guidelines
- Follow the repo’s pattern: `<scope>: <concise message> (#NNN)` (see `git log`), where scope is the touched area (e.g., `auth`, `tui`, `fix`).
- Keep commits focused; include tests and formatting in the same change when practical.
- PRs should describe behavior changes, list key commands run (e.g., tests/build), link related issues, and include before/after notes or screenshots for UI/TUI updates.
- Check in `uv.lock` changes when dependency versions move; avoid committing secrets or local config.

### Contribution standards (agents-first)
- Keep PRs minimally scoped; prefer multiple PRs over one large PR when it reduces risk and review load.
- Include tests for behavior changes (unit/integration/e2e as appropriate). If you can’t add tests, explain why and what manual verification you performed.
- For UI/TUI changes, snapshot tests are the preferred evidence. If snapshots aren't available/appropriate, include screenshots (and note the terminal size used).
- Before opening a PR, run this verification flow (and include the exact commands run in the PR description):
  1. `make lint`
  2. `make test`
  3. If you touched ACP / end-to-end UI flow code (e.g., `e2e_tests/`, `openhands_cli/acp_impl/`, `openhands_cli/mcp/`, auth/connection flow): `uv run pytest e2e_tests`
  4. If you touched TUI code (e.g., `openhands_cli/tui/`, widgets, styles, layout): `uv run pytest tests/snapshots -v` (use `--snapshot-update` only for intentional UI changes)

#### PR submission checklist
- [ ] Scope is minimal and focused on one change
- [ ] Tests added/updated for behavior changes (or PR explains why not)
- [ ] `make lint`
- [ ] `make test`
- [ ] (If ACP/UI flow touched) `uv run pytest e2e_tests`
- [ ] (If TUI touched) snapshot tests run and snapshots updated/reviewed
- [ ] PR description includes: what changed, why, commands run, and UI evidence (snapshots/screenshots)

## Security & Configuration Tips
- Do not embed API keys or endpoints in code; rely on runtime configuration/env vars when integrating new services.
- When packaging, verify no sensitive files are included in `dist/`; adjust `openhands-cli.spec` if new assets are added.
