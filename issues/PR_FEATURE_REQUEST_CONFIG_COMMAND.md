## Add `/config` to configure model, provider, and settings

**Feature Request**

### Problem
Users cannot change model, provider, API key, or other agent settings from inside the CLI chat. The settings screen only appeared on first run; existing users had no way to reconfigure without restarting.

### Proposed Solution
Add a `/config` slash command that opens the same settings TUI as first-run (model, provider, API key, memory condensation).

**Behavior:**
- `/config` → opens the Agent Settings screen (same UI as first-run setup)
- Uses `action_open_settings()` with `show_cli_tab=False` so only Agent Settings is shown
- Blocked when a conversation is running (shows warning)
- Save works correctly—CLI settings are only saved when the CLI tab is shown

### Scope
- Slash-command wiring (`/config` → `action_open_settings()`)
- `SettingsScreen` supports `show_cli_tab` and `force_initial_setup_ui` for same-as-first-run layout
- Save logic uses `show_cli_tab` (not `is_initial_setup`) to avoid querying missing `#cli_settings_tab`

### Acceptance Criteria
- [x] `/config` opens the settings screen
- [x] Same TUI as first-run (Agent Settings only, no tab bar)
- [x] Save succeeds without "No nodes match '#cli_settings_tab'" error
- [x] Blocked when conversation is running (shows warning)

### Note
Agent settings changes require reopening the CLI to take effect.
