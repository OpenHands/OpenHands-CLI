# Repository Guidelines

## Repository Purpose & Context
- OpenHands CLI is a standalone terminal interface (Textual TUI) for interacting with the OpenHands agent.
- This repo ports legacy CLI code from the main OpenHands repository (`openhands/cli`) and refactors it to use the OpenHands agent-sdk (`openhands-sdk`, `openhands-tools`).
- When you need reference behavior/UI: consult upstream OpenHands. When you need agent behavior/tooling details: consult the agent-sdk repo.

## Project Structure & Module Organization
- `openhands_cli/`: Core CLI/TUI code (`entrypoint.py`, `tui/`, `auth/`, `mcp/`, `cloud/`, `user_actions/`, `conversations/`, `theme.py`, helpers in `utils.py`). Keep new modules snake_case and colocate tests.
- `tests/`: Pytest suite covering units, integration, and snapshot tests; mirrors source layout. `e2e_tests/`: end-to-end ACP/UI flows.
- `scripts/acp/`: JSON-RPC and debug helpers for ACP development; `hooks/`: PyInstaller/runtime hooks.
- Tooling & packaging: `Makefile` for common tasks, `build.sh`/`build.py` for PyInstaller artifacts, `openhands-cli.spec` for the frozen binary, `uv.lock` for resolved deps.
- `.openhands/`: agent-specific guidance; avoid adding extra root-level docs unless explicitly requested.

## Setup, Build, and Development Commands
- `make install`: `uv sync`
- `make install-dev`: `uv sync --group dev`
- `make build`: checks uv version, runs `uv sync --dev`, and installs pre-commit hooks (`uv run pre-commit install`).
- `make lint`: run all pre-commit hooks (`uv run pre-commit run --all-files`) — run before committing.
- `make format`: `uv run ruff format openhands_cli/`
- `make run` (or `uv run openhands`): launch the CLI; `uv run openhands-acp` for the ACP entrypoint.
- `make test`: `uv run pytest` (use `-m "not integration"` to skip slower paths). `uv run pytest e2e_tests` runs end-to-end flows.
- Packaging: `./build.sh --install-pyinstaller` produces binaries in `dist/`.

## Coding Style & Naming Conventions
- Python 3.12, ruff formatting (88-char line limit, double quotes).
- Ruff enforced rules: pycodestyle, pyflakes, isort, pyupgrade, unused-arg checks (tests allow fixture-style args), and guards against mutable defaults.
- Prefer modern typing syntax (`X | None` over `Optional[X]`) in new code.
- Keep modules/dirs snake_case; classes in CapWords; user-facing commands/flags kebab-case as in existing entrypoints.
- Type checking via `pyright` (`uv run pyright`); prefer type hints on new functions and public interfaces.

## Testing Guidelines
- Pytest discovery: files `test_*.py`, classes `Test*`, functions `test_*`. Use `@pytest.mark.integration` for costly flows.
- Match test locations to implementation (`tests/<area>/test_<module>.py`); add fixtures in `tests/conftest.py` when shared.
- Run `make test` before PRs.

### Snapshot testing (pytest-textual-snapshot)
- Run snapshot tests: `uv run pytest tests/snapshots -v`
- Update snapshots (intentional UI changes): `uv run pytest tests/snapshots --snapshot-update`
- Test files live under `tests/snapshots/`; generated SVG snapshots live under `tests/snapshots/__snapshots__/`.

## Dependency update playbook (agent-sdk / openhands-sdk)
If asked to “update the agent-sdk SHA” / bump `openhands-sdk` / `openhands-tools`:
1. Use `$GITHUB_TOKEN` to find the latest commit/tag in the agent-sdk repository.
2. Update the dependency pins in `pyproject.toml` (version or git `rev`).
3. Regenerate `uv.lock` (e.g., `uv sync`).
4. Run `./build.sh` to validate.
5. Open a PR. If the build fails, still open the PR and describe the failure and next steps.

## Documentation Guidelines
- Don’t add new root-level `.md` files or “summary updates” to `README.md` unless explicitly requested (use this `AGENTS.md` for repo guidance).

## Commit & Pull Request Guidelines
- Follow the repo’s pattern: `<scope>: <concise message> (#NNN)` (see `git log`), where scope is the touched area (e.g., `auth`, `tui`, `fix`).
- Keep commits focused; include tests and formatting in the same change when practical.
- PRs should describe behavior changes, list key commands run (e.g., tests/build), link related issues, and include before/after notes or screenshots for UI/TUI updates.
- Check in `uv.lock` changes when dependency versions move; avoid committing secrets or local config.

## Security & Configuration Tips
- Do not embed API keys or endpoints in code; rely on runtime configuration/env vars when integrating new services.
- When packaging, verify no sensitive files are included in `dist/`; adjust `openhands-cli.spec` if new assets are added.
