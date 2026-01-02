# Repository Purpose
This is the OpenHands CLI - a command-line interface for OpenHands AI Agent with Terminal User Interface (TUI) support. It provides a standalone executable that allows users to interact with OpenHands through a terminal interface.

This project ports CLI code from `https://github.com/All-Hands-AI/OpenHands` (folder `openhands/cli`) and refactors it to use the new agent-sdk from `https://github.com/All-Hands-AI/agent-sdk`.

## References
- Example script for agent-sdk: `https://github.com/All-Hands-AI/agent-sdk/blob/main/examples/hello_world.py`
- Use `$GITHUB_TOKEN` to refer to OpenHands repo for copying UI and user interactions for the CLI
- Refer to agent-sdk repo for setting up agent behavior, tools, etc.

# Setup Instructions
To set up the development environment:
1. Install dependencies: `make install-dev`
2. Install pre-commit hooks: `make install-pre-commit-hooks`



# Development Guidelines

## Linting Requirements
**Always run lint before committing changes.** Use `make lint` to run all pre-commit hooks on all files. The project uses:

## Typing Requirements
When using types, prefer modern typing syntax (e.g., use `| None` instead of `Optional`).

## Documentation Guidelines
- **Do NOT send summary updates in the README.md** for the repository
- **Do NOT create .md files in the root** of the repository to track or send updates
- Only make documentation changes when explicitly requested to

## Updating Agent-SDK SHA

If the user says something along the lines of "update the sha" or "update the agent-sdk sha", you need to:

1. Use the `$GITHUB_TOKEN` to get the latest commit from the agent-sdk repository
2. Update the poetry toml file with the new SHA
3. Regenerate the uv lock file
4. Run `./build.sh` to confirm that the build still works
5. Open a pull request with the changes

If the build fails, still open the pull request and explain what error you're seeing, and the steps you plan to take to fix it; don't fix it yet though.

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
   https://work-1-eidmcsndvfctphkv.prod-runtime.all-hands.dev/<snapshot-name>.svg
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

### Best Practices

1. **Mock external dependencies** - Use `unittest.mock.patch` to ensure deterministic snapshots
2. **Use fixed terminal sizes** - Always specify `terminal_size=(width, height)` for consistent results
3. **Commit snapshots to git** - SVG files are test artifacts and should be version controlled
4. **Review snapshot diffs carefully** - When tests fail, examine the visual diff to determine if the change is intentional