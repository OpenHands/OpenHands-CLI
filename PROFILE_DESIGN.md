# LLM Profile Management Design Document

## Overview

This document outlines the design for the LLM Profile Management feature in OpenHands CLI, addressing:
1. Easy switching between different LLM models and providers
2. Support for OpenHands Cloud provider with automatic access to all verified LLMs
3. Integration of MCP (Model Context Protocol) configurations into profiles
4. Making profiles comprehensive (LLM + MCP + other agent settings)

## Core Design Principles

### 1. Profile = Complete Agent Configuration

A profile is not just an LLM configuration—it's a **complete agent specification** including:
- LLM configuration (model, API key, base_url, etc.)
- MCP configuration (mcpServers from cloud or local)
- Condenser configuration
- Agent context settings
- Security analyzer settings (deprecated but for backward compat)

**Rationale**: This allows users to have different complete environments for different use cases, not just different models. For example, a "research" profile might use GPT-4 with specific MCP tools, while a "coding" profile uses Claude with different MCP configurations.

### 2. OpenHands Cloud Provider Integration

When users authenticate with the OpenHands Cloud provider:
- They automatically get access to ALL verified LLMs
- Profiles are auto-generated for each verified model
- Updates are synchronized when CLI version changes or user manually syncs
- Cloud-provided MCP configurations are automatically included

**Rationale**: Eliminates manual setup for cloud users and ensures they always have access to the latest verified models.

### 3. Hierarchical Configuration with MCP

MCP configurations can be defined at multiple levels:
1. **Global cloud default**: Applied to all OpenHands cloud models
2. **Model-specific cloud config**: Overrides for specific models in the cloud
3. **User profile config**: User customizations per profile

**Merge Strategy**: User profile > Model-specific cloud > Global cloud > Local default

**Rationale**: Provides flexibility while maintaining sensible defaults. Users can customize as needed without losing cloud updates.

## Directory Structure

```
~/.openhands/
├── llms/                                    # Profile directory (NEW)
│   ├── default.json                         # Symlink to default profile
│   ├── profiles.json                        # Profile metadata and cloud sync info
│   ├── .last_opened_version                 # CLI version tracking (DEPRECATED - moved to profiles.json)
│   │
│   ├── my-gpt4.json                        # User-created profiles
│   ├── claude-sonnet.json
│   ├── local-ollama.json
│   │
│   ├── openhands-general.json              # Base config for OpenHands cloud
│   ├── openhands-gpt-4o-mini.json          # Auto-generated cloud profiles
│   ├── openhands-claude-3-5-sonnet.json
│   └── openhands-gpt-4.json
│
├── conversations/                           # Existing conversations directory
├── agent_settings.json                      # LEGACY (migrated to llms/default.json)
└── mcp.json                                # LEGACY (migrated into profiles)
```

## Configuration File Formats

### profiles.json (Profile Metadata)

```json
{
  "version": "1.0",
  "default_profile": "my-gpt4",
  "last_opened_version": "0.9.0",
  
  "profiles": [
    {
      "name": "my-gpt4",
      "file": "my-gpt4.json",
      "description": "My custom GPT-4 setup",
      "type": "user",
      "created_at": "2025-11-18T10:00:00Z",
      "last_used": "2025-11-18T10:30:00Z",
      "tags": ["work", "complex-tasks"]
    },
    {
      "name": "openhands-gpt-4o-mini",
      "file": "openhands-gpt-4o-mini.json",
      "description": "OpenHands Cloud - GPT-4o Mini",
      "type": "openhands-cloud",
      "provider": "openhands",
      "model_id": "gpt-4o-mini",
      "auto_generated": true,
      "generated_version": "0.9.0",
      "created_at": "2025-11-18T10:00:00Z",
      "last_used": "2025-11-18T09:00:00Z"
    }
  ],
  
  "openhands_cloud": {
    "enabled": true,
    "auth_token": "encrypted_token_here",
    "last_sync": "2025-11-18T10:00:00Z",
    
    "verified_models": [
      {
        "model": "gpt-4o-mini",
        "display_name": "GPT-4o Mini",
        "provider": "openai",
        "capabilities": ["chat", "tools"],
        "recommended_use": "Fast iterations, simple tasks"
      },
      {
        "model": "claude-3-5-sonnet",
        "display_name": "Claude 3.5 Sonnet",
        "provider": "anthropic",
        "capabilities": ["chat", "tools", "vision"],
        "recommended_use": "Code generation, analysis"
      },
      {
        "model": "gpt-4",
        "display_name": "GPT-4",
        "provider": "openai",
        "capabilities": ["chat", "tools", "vision"],
        "recommended_use": "Complex reasoning, challenging tasks"
      }
    ],
    
    "mcp_configs": {
      "default": {
        "mcpServers": {
          "browser": {
            "command": "mcp-server-browser",
            "args": []
          }
        }
      },
      "by_model": {
        "gpt-4": {
          "mcpServers": {
            "browser": {
              "command": "mcp-server-browser",
              "args": []
            },
            "github": {
              "command": "mcp-server-github",
              "args": ["--token", "${GITHUB_TOKEN}"]
            }
          }
        }
      }
    }
  }
}
```

### Individual Profile File (e.g., my-gpt4.json)

Each profile file contains a **complete Agent configuration**:

```json
{
  "llm": {
    "model": "openai/gpt-4",
    "api_key": "sk-...",
    "base_url": null,
    "temperature": 0.7,
    "max_tokens": 4096
  },
  
  "mcp_config": {
    "mcpServers": {
      "filesystem": {
        "command": "mcp-server-filesystem",
        "args": ["/workspace"]
      },
      "github": {
        "command": "mcp-server-github",
        "args": ["--token", "${GITHUB_TOKEN}"]
      }
    }
  },
  
  "condenser": {
    "llm": {
      "model": "openai/gpt-4o-mini",
      "api_key": "sk-...",
      "base_url": null
    }
  },
  
  "tools": [],
  "agent_context": null
}
```

### openhands-general.json (Base Template for Cloud Profiles)

This serves as the base configuration for all auto-generated OpenHands cloud profiles:

```json
{
  "llm": {
    "model": "TO_BE_REPLACED",
    "api_key": "OPENHANDS_CLOUD_TOKEN",
    "base_url": "https://llm-proxy.openhands.ai/",
    "temperature": 0.7
  },
  
  "mcp_config": {
    "mcpServers": {}
  },
  
  "condenser": {
    "llm": {
      "model": "openai/gpt-4o-mini",
      "api_key": "OPENHANDS_CLOUD_TOKEN",
      "base_url": "https://llm-proxy.openhands.ai/"
    }
  },
  
  "tools": [],
  "agent_context": null
}
```

## User Experience

### 1. First-Time User Flow

```
$ openhands

Welcome to OpenHands!

No agent configuration found. Let's set up your first profile.

Choose setup method:
  1. Quick Start (OpenHands Cloud - Recommended)
  2. Custom Setup (Bring your own API keys)
  3. Advanced Setup (Full customization)

[User selects 1]

✓ Authenticating with OpenHands Cloud...
✓ Fetching verified models...
✓ Found 3 verified models: GPT-4o Mini, Claude 3.5 Sonnet, GPT-4

Which model would you like to use as default?
  1. GPT-4o Mini (Fast, economical)
  2. Claude 3.5 Sonnet (Best for coding)
  3. GPT-4 (Most capable)

[User selects 2]

✓ Created profile: openhands-claude-3-5-sonnet
✓ Auto-generated 2 additional profiles: openhands-gpt-4o-mini, openhands-gpt-4
✓ Set openhands-claude-3-5-sonnet as default

You can switch profiles anytime with: openhands --profile <name>
View all profiles with: openhands profiles list

Starting conversation with Claude 3.5 Sonnet...
```

### 2. Profile Selection at Conversation Start

**Option A: Command-line flag**
```bash
openhands --profile gpt4
openhands --profile openhands-claude-3-5-sonnet
```

**Option B: Interactive selection (no --profile flag)**
```
$ openhands

Select a profile:
  → openhands-claude-3-5-sonnet (Claude 3.5 Sonnet) [default]
    openhands-gpt-4o-mini (GPT-4o Mini)
    openhands-gpt-4 (GPT-4)
    my-custom-gpt4 (My custom GPT-4 setup)
    ─────────────────────────────────
    Create new profile...
    Manage profiles...
    Sync cloud profiles...

[Use ↑↓ to select, Enter to confirm, Ctrl+C to exit]

✓ Starting conversation with Claude 3.5 Sonnet...
```

### 3. Profile Management Commands

```bash
# List all profiles
$ openhands profiles list
Available profiles:
  * openhands-claude-3-5-sonnet  Claude 3.5 Sonnet (OpenHands Cloud) [default]
    openhands-gpt-4o-mini        GPT-4o Mini (OpenHands Cloud)
    openhands-gpt-4              GPT-4 (OpenHands Cloud)
    my-custom-gpt4               My custom GPT-4 setup (User)
    local-ollama                 Local Ollama llama3 (User)

# Create new profile interactively
$ openhands profiles create my-new-profile
Creating new profile: my-new-profile

Choose base configuration:
  1. Start from scratch
  2. Copy from existing profile
  3. Use OpenHands Cloud model

[Interactive wizard follows...]

# Edit existing profile
$ openhands profiles edit my-custom-gpt4
Editing profile: my-custom-gpt4

What would you like to edit?
  1. LLM settings (model, API key, etc.)
  2. MCP configuration
  3. Condenser settings
  4. Description and metadata

# Delete profile
$ openhands profiles delete my-old-profile
Are you sure you want to delete profile 'my-old-profile'? [y/N]: y
✓ Profile deleted

# Set default profile
$ openhands profiles set-default my-custom-gpt4
✓ Set 'my-custom-gpt4' as default profile

# Sync cloud profiles (refresh from OpenHands Cloud)
$ openhands profiles sync
Syncing with OpenHands Cloud...
✓ Found 3 verified models
✓ Updated openhands-gpt-4o-mini
✓ Updated openhands-claude-3-5-sonnet
✓ Updated openhands-gpt-4
✓ Sync complete

# Show profile details
$ openhands profiles show my-custom-gpt4
Profile: my-custom-gpt4
Description: My custom GPT-4 setup
Type: user
Created: 2025-11-18 10:00:00
Last used: 2025-11-18 10:30:00

LLM Configuration:
  Model: openai/gpt-4
  API Key: sk-...xyz (hidden)
  Base URL: (default)
  Temperature: 0.7

MCP Configuration:
  Servers: filesystem, github

Condenser:
  Model: openai/gpt-4o-mini
```

### 4. OpenHands Cloud Integration

```bash
# Login to OpenHands Cloud
$ openhands cloud login
Opening browser for authentication...
✓ Authenticated successfully
✓ Generating profiles for 3 verified models...
✓ Cloud integration enabled

# Logout from OpenHands Cloud
$ openhands cloud logout
✓ Removed cloud authentication
  Note: Existing cloud profiles will remain but won't be updated

# Check cloud status
$ openhands cloud status
OpenHands Cloud: Connected
Last sync: 2025-11-18 10:00:00
Verified models: 3
Auto-sync: enabled
```

## Implementation Plan

### Phase 1: Core Profile Infrastructure

#### 1.1 Update locations.py
```python
PROFILES_DIR = os.path.join(PERSISTENCE_DIR, "llms")
PROFILES_CONFIG_PATH = os.path.join(PROFILES_DIR, "profiles.json")
DEFAULT_PROFILE_PATH = os.path.join(PROFILES_DIR, "default.json")
OPENHANDS_GENERAL_PATH = os.path.join(PROFILES_DIR, "openhands-general.json")

# Legacy paths for migration
LEGACY_AGENT_SETTINGS_PATH = os.path.join(PERSISTENCE_DIR, "agent_settings.json")
LEGACY_MCP_CONFIG_PATH = os.path.join(PERSISTENCE_DIR, "mcp.json")
```

#### 1.2 Create ProfileManager class
**File**: `openhands_cli/tui/settings/profile_manager.py`

```python
class ProfileManager:
    """Manages profile operations: create, load, save, delete, list."""
    
    def __init__(self, profiles_dir: Path):
        self.profiles_dir = profiles_dir
        self.config_path = profiles_dir / "profiles.json"
        self._ensure_directories()
    
    def list_profiles(self) -> list[ProfileInfo]:
        """List all available profiles"""
        
    def load_profile(self, name: str) -> Agent:
        """Load a specific profile by name"""
        
    def save_profile(self, name: str, agent: Agent, description: str = "") -> None:
        """Save an agent configuration as a profile"""
        
    def delete_profile(self, name: str) -> None:
        """Delete a profile"""
        
    def get_default_profile(self) -> str:
        """Get the name of the default profile"""
        
    def set_default_profile(self, name: str) -> None:
        """Set the default profile"""
```

#### 1.3 Create CloudProfileGenerator class
**File**: `openhands_cli/tui/settings/cloud_profile_generator.py`

```python
class CloudProfileGenerator:
    """Auto-generates profiles from OpenHands Cloud metadata."""
    
    def __init__(self, profile_manager: ProfileManager):
        self.profile_manager = profile_manager
    
    def sync_cloud_profiles(self) -> None:
        """Sync profiles with OpenHands Cloud"""
        
    def generate_profile_for_model(self, model_info: dict) -> Agent:
        """Generate a profile for a specific verified model"""
        
    def check_version_and_update(self, current_version: str) -> None:
        """Check if CLI version changed and regenerate profiles"""
```

#### 1.4 Migration Logic
**File**: `openhands_cli/tui/settings/migration.py`

```python
class ProfileMigration:
    """Handles migration from legacy configuration to profile system."""
    
    def migrate_if_needed(self) -> None:
        """Check if migration is needed and perform it"""
        
    def migrate_agent_settings(self) -> None:
        """Migrate agent_settings.json to llms/default.json"""
        
    def migrate_mcp_config(self) -> None:
        """Migrate mcp.json into default profile"""
```

### Phase 2: User Interface Components

#### 2.1 Profile Selection UI
**File**: `openhands_cli/tui/profile_selector.py`

```python
class ProfileSelector:
    """Interactive profile selection UI"""
    
    def select_profile(self) -> str:
        """Display profile list and return selected profile name"""
        
    def display_profile_details(self, profile_name: str) -> None:
        """Show detailed information about a profile"""
```

#### 2.2 Profile Management Actions
**File**: `openhands_cli/user_actions/profile_actions.py`

```python
class ProfileCreationWizard:
    """Interactive wizard for creating new profiles"""
    
class ProfileEditor:
    """Interactive editor for modifying profiles"""
    
class ProfileDeleter:
    """Handle profile deletion with confirmation"""
```

### Phase 3: CLI Integration

#### 3.1 Update main_parser.py
Add `--profile` argument and `profiles` subcommand:

```python
parser.add_argument("--profile", type=str, help="Profile name to use")

profiles_parser = subparsers.add_parser("profiles", help="Manage LLM profiles")
profiles_subparsers = profiles_parser.add_subparsers(dest="profiles_command")

# Add subcommands: list, create, edit, delete, set-default, sync, show
```

#### 3.2 Update setup.py
Modify `setup_conversation()` to accept profile parameter:

```python
def setup_conversation(
    conversation_id: UUID,
    profile_name: str | None = None,
    include_security_analyzer: bool = True
) -> BaseConversation:
    """Setup conversation with specified profile"""
    
    profile_manager = ProfileManager(PROFILES_DIR)
    
    if not profile_name:
        profile_name = profile_manager.get_default_profile()
    
    agent = profile_manager.load_profile(profile_name)
    # ... rest of setup
```

#### 3.3 Update simple_main.py
Add profile command handling and pass profile to conversation setup.

### Phase 4: Testing

#### 4.1 Unit Tests
- `tests/profiles/test_profile_manager.py` - Profile CRUD operations
- `tests/profiles/test_cloud_generator.py` - Cloud profile generation
- `tests/profiles/test_migration.py` - Migration from legacy config
- `tests/profiles/test_profile_selection.py` - Profile selection logic

#### 4.2 Integration Tests
- `tests/profiles/test_profile_workflow.py` - End-to-end profile workflows
- `tests/profiles/test_cloud_integration.py` - Cloud sync integration

## Backward Compatibility

### Migration Strategy

1. **On first launch after upgrade**:
   - Check if `llms/profiles.json` exists
   - If not, perform migration:
     * Move `agent_settings.json` → `llms/default.json`
     * Merge `mcp.json` into default profile
     * Create `profiles.json` with default profile metadata
     * Set "default" as the default profile

2. **Command compatibility**:
   - If no `--profile` is specified, use default profile
   - Existing workflows continue to work unchanged

3. **Settings flow**:
   - Settings screen continues to work but now saves to active profile
   - If no profile exists, create "default" profile

### Feature Flags

Consider adding feature flags for gradual rollout:
- `PROFILES_ENABLED` - Enable/disable profile system
- `CLOUD_PROFILES_ENABLED` - Enable/disable cloud profile generation
- `AUTO_SYNC_ENABLED` - Enable/disable automatic cloud sync

## Security Considerations

1. **API Key Storage**:
   - Continue using existing secure storage mechanism
   - API keys in profiles remain encrypted

2. **Cloud Authentication**:
   - Store cloud auth token securely (encrypted)
   - Implement token refresh mechanism
   - Allow easy logout/revocation

3. **Profile Sharing**:
   - Warn users when exporting profiles (API keys included)
   - Provide option to export without sensitive data

## Future Enhancements

### Phase 5: Advanced Features (Post-MVP)

1. **Profile Import/Export**
   ```bash
   openhands profiles export my-profile > profile.json
   openhands profiles import < profile.json
   ```

2. **Profile Templates**
   ```bash
   openhands profiles create-from-template coding
   openhands profiles create-from-template research
   ```

3. **Team Workspace Profiles**
   - Shared profiles for team collaboration
   - Version control integration

4. **Profile Usage Analytics**
   - Track which profiles are used most
   - Suggest optimal profiles based on task type

5. **Smart Profile Switching**
   - Auto-switch based on project directory
   - Switch based on task type (code review vs. research)

6. **Profile Inheritance**
   - Create profiles that inherit from base profiles
   - Override only specific settings

## Open Questions

1. **MCP Override Strategy**: Should user-defined MCP configs completely replace cloud configs, or merge with them?
   - **Proposal**: Merge by default, with option to replace entirely

2. **Profile Naming**: Should we enforce naming conventions for OpenHands cloud profiles?
   - **Proposal**: Yes, use `openhands-<model-id>` format for consistency

3. **Sync Frequency**: How often should we sync with OpenHands Cloud?
   - **Proposal**: On version change, daily auto-sync, and manual sync command

4. **Profile Validation**: Should we validate profiles before saving?
   - **Proposal**: Yes, validate that required fields exist and LLM config is valid

5. **Conflict Resolution**: What happens if user edits an auto-generated cloud profile?
   - **Proposal**: Convert to user profile type, stop auto-updating it

## Success Metrics

- Reduction in time to switch between models
- Increase in number of models tried per user
- User satisfaction with profile management
- Adoption rate of OpenHands Cloud profiles
- Number of custom profiles created per user

## Conclusion

This design provides:
- ✅ Easy switching between different LLM models and providers
- ✅ Automatic access to all verified OpenHands Cloud models
- ✅ MCP integration into profiles (profile = LLM + MCP + more)
- ✅ Backward compatibility with existing configuration
- ✅ Extensible architecture for future enhancements
- ✅ Automatic profile generation and updates for cloud users
- ✅ Hierarchical configuration with sensible defaults

The key innovation is treating profiles as **complete agent configurations** rather than just LLM settings, combined with **automatic generation** of cloud profiles and **version-tracked synchronization** to ensure users always have access to the latest verified models.
