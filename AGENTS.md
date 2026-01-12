# Repository Guidelines

## Repository Purpose
OpenHands CLI is a standalone terminal interface (Textual TUI) for interacting with the OpenHands agent.

This repo contains the current CLI UX, including the Textual TUI and a browser-served view via `openhands web`.

The CLI originated as a port from the main OpenHands repository (`openhands/cli`) and was refactored to use the OpenHands agent-sdk (`openhands-sdk`, `openhands-tools`). Upstream OpenHands can still be a useful reference for behavior parity and shared concepts.

### References
- Agent-sdk example: https://github.com/All-Hands-AI/agent-sdk/blob/main/examples/hello_world.py
- If you need to compare with upstream OpenHands code, use `$GITHUB_TOKEN` for access.

## Project Structure & Module Organization
- `openhands_cli/`: Core CLI/TUI code (`entrypoint.py`, `tui/`, `auth/`, `mcp/`, `cloud/`, `user_actions/`, `conversations/`, `theme.py`, helpers in `utils.py`). Keep new modules snake_case and colocate tests.
- `tests/`: Pytest suite covering units, integration, and snapshot tests; mirrors source layout. `e2e_tests/`: end-to-end ACP/UI flows.
- `scripts/acp/`: JSON-RPC and debug helpers for ACP development; `hooks/`: PyInstaller/runtime hooks.
- Tooling & packaging: `Makefile` for common tasks, `build.sh`/`build.py` for PyInstaller artifacts, `openhands-cli.spec` for the frozen binary, `uv.lock` for resolved deps.
- `.openhands/skills/`: agent guidance for this repo.
  - `.openhands/skills/repo.md` is a symlink to the root `AGENTS.md` (single source of truth).

## Setup Instructions
To set up the development environment:
1. Install dependencies: `make install-dev`
2. Install pre-commit hooks: `make install-pre-commit-hooks`

## Setup, Build, and Development Commands
- `make install`: `uv sync`
- `make install-dev`: `uv sync --group dev`
- `make install-pre-commit-hooks`: install pre-commit hooks.
- `make build`: checks uv version, runs `uv sync --dev`, and installs pre-commit hooks (`uv run pre-commit install`).
- `make lint`: run all pre-commit hooks (`uv run pre-commit run --all-files`) — run before committing.
- `make format`: `uv run ruff format openhands_cli/`
- `make run` (or `uv run openhands`): launch the Textual TUI.
- `openhands web`: launch the CLI as a browser-served web app (Textual `textual-serve`).
- `openhands serve`: launch the Docker-based OpenHands GUI server.
- `uv run openhands-acp`: run the ACP entrypoint.
- `make test`: `uv run pytest` (use `-m "not integration"` to skip slower paths). `uv run pytest e2e_tests` runs end-to-end flows.
- Packaging: `./build.sh --install-pyinstaller` produces binaries in `dist/`.

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
- Match test locations to implementation (`tests/<area>/test_<module>.py`); add fixtures in `tests/conftest.py` when shared.
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
- **Test files**: `tests/snapshots/test_app_snapshots.py`
- **Generated snapshots**: `tests/snapshots/__snapshots__/test_app_snapshots/*.svg`

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
   - `TestOpenHandsAppSnapshots.test_openhands_app_splash_screen.svg`
   - `TestInputFieldSnapshots.test_input_field_with_text.svg`

3. **Stop the server** when done:
   ```bash
   pkill -f "python -m http.server 12000"
   ```

### Current Snapshot Tests

| Test Class | Test Name | Description |
|------------|-----------|-------------|
| `TestExitModalSnapshots` | `test_exit_modal_initial_state` | Exit confirmation modal initial view |
| `TestExitModalSnapshots` | `test_exit_modal_with_focus_on_yes` | Exit modal with focus on Yes button |
| `TestInputFieldSnapshots` | `test_input_field_single_line_mode` | Input field in default state |
| `TestInputFieldSnapshots` | `test_input_field_with_text` | Input field with typed text |
| `TestOpenHandsAppSnapshots` | `test_openhands_app_splash_screen` | Main app splash screen (mocked) |
| `TestConfirmationModalSnapshots` | `test_confirmation_settings_modal` | Confirmation settings modal |

### Snapshot Best Practices
- Mock external dependencies so snapshots are deterministic.
- Always pass a fixed `terminal_size=(width, height)`.
- Commit SVG snapshots.
- Review snapshot diffs carefully.

## Updating Agent-SDK SHA (agent-sdk / openhands-sdk)
If asked to “update the agent-sdk SHA” / bump `openhands-sdk` / `openhands-tools`:
1. Use `$GITHUB_TOKEN` to find the latest commit/tag in the agent-sdk repository.
2. Update the dependency pins in `pyproject.toml` (version or git `rev`).
3. Regenerate the `uv.lock` file (e.g., `uv sync`).
4. Run `./build.sh` to confirm that the build still works.
5. Open a PR. If the build fails, still open the PR and describe what error you’re seeing and the next steps; don’t fix it yet.

## Commit & Pull Request Guidelines
- Follow the repo’s pattern: `<scope>: <concise message> (#NNN)` (see `git log`), where scope is the touched area (e.g., `auth`, `tui`, `fix`).
- Keep commits focused; include tests and formatting in the same change when practical.
- PRs should describe behavior changes, list key commands run (e.g., tests/build), link related issues, and include before/after notes or screenshots for UI/TUI updates.
- Check in `uv.lock` changes when dependency versions move; avoid committing secrets or local config.

## Security & Configuration Tips
- Do not embed API keys or endpoints in code; rely on runtime configuration/env vars when integrating new services.
- When packaging, verify no sensitive files are included in `dist/`; adjust `openhands-cli.spec` if new assets are added.
