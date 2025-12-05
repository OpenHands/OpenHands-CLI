# Design Review Response: Profile System for OpenHands Cloud & MCP Integration

## Questions Addressed

### Q1: How to support ALL verified LLMs under OpenHands Cloud provider with easy switching?

**Proposed Solution**: Automatic Profile Generation with Version Tracking

Instead of the naive approach of maintaining just `llms/openhands-general.json` and using `.last_opened_version` as a separate file, I propose:

#### Enhanced Structure:
```
~/.openhands/
└── llms/
    ├── profiles.json                        # Contains EVERYTHING including:
    │                                        #   - Profile metadata
    │                                        #   - last_opened_version (embedded)
    │                                        #   - OpenHands cloud config
    │                                        #   - Verified models list
    │
    ├── openhands-general.json              # Base template for cloud profiles
    ├── openhands-gpt-4o-mini.json          # Auto-generated profiles
    ├── openhands-claude-3-5-sonnet.json
    └── openhands-gpt-4.json
```

#### How It Works:

1. **Initial Cloud Login**:
   ```bash
   $ openhands cloud login
   ✓ Authenticated with OpenHands Cloud
   ✓ Fetching verified models... Found 3 models
   ✓ Generating profile for gpt-4o-mini
   ✓ Generating profile for claude-3-5-sonnet  
   ✓ Generating profile for gpt-4
   ```
   - Fetch list of verified models from cloud API
   - For each verified model, generate `llms/openhands-<model_name>.json`
   - Store metadata in `profiles.json`:
     ```json
     {
       "last_opened_version": "0.9.0",
       "openhands_cloud": {
         "enabled": true,
         "verified_models": [...]
       }
     }
     ```

2. **Version Change Detection**:
   ```python
   # On CLI startup
   current_version = get_current_cli_version()  # e.g., "0.10.0"
   last_version = profiles_json["last_opened_version"]  # e.g., "0.9.0"
   
   if current_version != last_version and openhands_cloud["enabled"]:
       # Re-fetch verified models from cloud
       # Regenerate all openhands-* profiles
       # Update last_opened_version to current_version
   ```

3. **Easy Switching**:
   ```bash
   # At conversation start
   $ openhands
   
   Select a profile:
     → openhands-gpt-4o-mini (GPT-4o Mini - Fast iterations)
       openhands-claude-3-5-sonnet (Claude 3.5 Sonnet - Best for coding)
       openhands-gpt-4 (GPT-4 - Complex reasoning)
       my-custom-profile (My custom setup)
   
   # Or via command line
   $ openhands --profile openhands-gpt-4
   $ openhands --profile openhands-claude-3-5-sonnet
   ```

#### Advantages Over Naive Approach:

| Naive Approach | Enhanced Approach |
|----------------|-------------------|
| Separate `.last_opened_version` file | Embedded in `profiles.json` (single source of truth) |
| Simple file existence check | Rich metadata with timestamps, model capabilities, descriptions |
| No user feedback during generation | Progress indicators and success messages |
| Regenerate all profiles blindly | Smart regeneration (only if version changed or user syncs) |
| No cloud status tracking | Track connection status, last sync time, auth state |
| Manual sync unclear | Explicit `openhands profiles sync` and `openhands cloud status` commands |

#### Implementation Details:

```python
# profiles.json structure
{
  "version": "1.0",
  "last_opened_version": "0.9.0",  # CLI version, not file format version
  
  "profiles": [
    {
      "name": "openhands-gpt-4o-mini",
      "type": "openhands-cloud",
      "auto_generated": true,
      "generated_version": "0.9.0",  # Track which version generated this
      "model_id": "gpt-4o-mini",
      # ... other metadata
    }
  ],
  
  "openhands_cloud": {
    "enabled": true,
    "last_sync": "2025-11-18T10:00:00Z",
    "verified_models": [
      {
        "model": "gpt-4o-mini",
        "display_name": "GPT-4o Mini",
        "recommended_use": "Fast iterations, simple tasks",
        "capabilities": ["chat", "tools"]
      }
      # ... more models
    ]
  }
}
```

#### Profile Generation Algorithm:

```python
def generate_cloud_profiles():
    """Generate profiles for all verified OpenHands cloud models."""
    
    # 1. Load base template
    base_template = load_json("openhands-general.json")
    
    # 2. Get verified models from cloud
    verified_models = fetch_verified_models_from_cloud()
    
    # 3. For each model, generate a profile
    for model_info in verified_models:
        profile = base_template.copy()
        
        # Replace model-specific fields
        profile["llm"]["model"] = model_info["model"]
        
        # Merge cloud MCP config if exists
        if model_info["model"] in cloud_mcp_configs["by_model"]:
            profile["mcp_config"] = merge_mcp_configs(
                cloud_mcp_configs["default"],
                cloud_mcp_configs["by_model"][model_info["model"]]
            )
        else:
            profile["mcp_config"] = cloud_mcp_configs["default"]
        
        # Save profile
        save_json(f"openhands-{model_info['model']}.json", profile)
        
        # Add to profiles.json metadata
        add_profile_metadata({
            "name": f"openhands-{model_info['model']}",
            "type": "openhands-cloud",
            "auto_generated": true,
            "generated_version": current_cli_version,
            # ... more metadata
        })
```

---

### Q2: How to support MCP defined in the cloud? Can we make a profile be LLM+MCP?

**Answer**: Yes! A profile should be **LLM + MCP + Everything Else** (complete agent configuration).

#### Why Profile = Complete Agent Config?

1. **MCP configurations are often model-specific**: GPT-4 might work well with certain MCP tools that Claude doesn't, or vice versa.

2. **Profiles represent complete environments**: Users don't just want to switch models, they want to switch entire setups.

3. **Already aligned with Agent model**: The `Agent` class already contains:
   - `llm`: LLM configuration
   - `mcp_config`: MCP configuration
   - `condenser`: Condenser configuration
   - `tools`: Tool list
   - `agent_context`: Agent context

#### Hierarchical MCP Configuration:

```
User Profile MCP
    ↓ (overrides)
Model-Specific Cloud MCP
    ↓ (overrides)
Global Cloud MCP
    ↓ (overrides)
Local Default MCP
```

#### Example Scenario:

**OpenHands Cloud provides**:
```json
{
  "openhands_cloud": {
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
            "browser": { ... },
            "github": {
              "command": "mcp-server-github",
              "args": ["--token", "${GITHUB_TOKEN}"]
            }
          }
        },
        "claude-3-5-sonnet": {
          "mcpServers": {
            "browser": { ... },
            "filesystem": {
              "command": "mcp-server-filesystem",
              "args": ["/workspace"]
            }
          }
        }
      }
    }
  }
}
```

**When generating `openhands-gpt-4.json`**:
```json
{
  "llm": {
    "model": "gpt-4",
    "api_key": "OPENHANDS_CLOUD_TOKEN",
    "base_url": "https://llm-proxy.openhands.ai/"
  },
  
  "mcp_config": {
    "mcpServers": {
      "browser": { ... },    // From cloud default
      "github": { ... }      // From model-specific cloud config (gpt-4)
    }
  },
  
  "condenser": {
    "llm": {
      "model": "gpt-4o-mini",
      "api_key": "OPENHANDS_CLOUD_TOKEN"
    }
  }
}
```

**User can customize**:
```bash
$ openhands profiles edit openhands-gpt-4

What would you like to edit?
  1. LLM settings
  2. MCP configuration  ← User selects this
  3. Condenser settings

Current MCP servers:
  ✓ browser
  ✓ github

Add a new server? [y/N]: y
Enter server name: slack
Enter command: mcp-server-slack
Enter args (comma-separated): --token,${SLACK_TOKEN}

✓ Added 'slack' to MCP configuration
✓ Profile updated

Note: This profile is now a custom profile and won't be auto-updated.
Convert to user profile? [Y/n]: y
✓ Converted to user profile: my-gpt-4-with-slack
```

**Result**:
- Original `openhands-gpt-4.json` remains (auto-updated)
- New `my-gpt-4-with-slack.json` created (user-managed, not auto-updated)
- User profile has cloud MCP + custom slack MCP

#### MCP Configuration Merge Strategy:

```python
def merge_mcp_configs(*configs):
    """Merge multiple MCP configurations with later ones overriding earlier."""
    result = {"mcpServers": {}}
    
    for config in configs:
        if not config or "mcpServers" not in config:
            continue
        
        for server_name, server_config in config["mcpServers"].items():
            # Later configs override earlier ones
            result["mcpServers"][server_name] = server_config
    
    return result

# Usage when loading profile
def load_profile_with_mcp(profile_name):
    profile = load_profile_json(profile_name)
    
    if profile["type"] == "openhands-cloud":
        # Merge cloud MCP with profile MCP
        cloud_default_mcp = get_cloud_default_mcp()
        cloud_model_mcp = get_cloud_model_mcp(profile["model_id"])
        profile_mcp = profile.get("mcp_config", {})
        
        profile["mcp_config"] = merge_mcp_configs(
            cloud_default_mcp,
            cloud_model_mcp,
            profile_mcp
        )
    
    return profile
```

#### Benefits:

1. **Cloud-provided MCP**: Users get sensible defaults from OpenHands Cloud
2. **Model-specific MCP**: Each model can have optimized MCP configurations
3. **User customization**: Users can override or extend cloud MCP configs
4. **Easy updates**: When cloud updates MCP configs, user gets them automatically (for auto-generated profiles)
5. **Flexibility**: Users can create fully custom profiles with their own MCP setups

---

## Summary of Design Decisions

### 1. Profile Structure
- ✅ Profile = Complete Agent Configuration (LLM + MCP + Condenser + More)
- ✅ Not just LLM settings

### 2. Cloud Integration
- ✅ Automatic profile generation for all verified models
- ✅ Version-tracked regeneration using `last_opened_version` in `profiles.json`
- ✅ Manual sync command: `openhands profiles sync`
- ✅ Cloud status tracking: `openhands cloud status`

### 3. MCP Integration
- ✅ MCP defined at multiple levels: Global Cloud → Model-Specific Cloud → User Profile
- ✅ Hierarchical merge strategy with user overrides
- ✅ Cloud-provided MCP automatically included in generated profiles
- ✅ Users can customize without losing cloud updates (by creating custom profiles)

### 4. File Structure
```
llms/
├── profiles.json           # Single source of truth for:
│                          #   - Profile metadata
│                          #   - last_opened_version
│                          #   - Cloud config & verified models
│                          #   - MCP cloud configs
├── default.json           # Symlink to default profile
├── openhands-general.json # Base template
└── *.json                # Individual profile files
```

### 5. User Experience
- Auto-generation on cloud login
- Auto-regeneration on version change
- Easy switching with `--profile` flag or interactive selector
- Clear distinction between auto-generated and user profiles
- Convert cloud profile to user profile to prevent auto-updates

---

## Implementation Priorities

### Phase 1: Core Infrastructure ⭐ MUST HAVE
1. ProfileManager class
2. Profile storage and loading
3. Migration from legacy config
4. Basic CLI integration (--profile flag)

### Phase 2: Cloud Integration ⭐ MUST HAVE (for your use case)
1. CloudProfileGenerator class
2. Version tracking and auto-regeneration
3. Verified models fetching
4. Cloud MCP configuration support

### Phase 3: User Interface ⭐ SHOULD HAVE
1. Interactive profile selector
2. Profile management commands (list, create, edit, delete)
3. Cloud commands (login, logout, status, sync)

### Phase 4: Polish ✨ NICE TO HAVE
1. Profile usage analytics
2. Import/export
3. Profile templates
4. Smart profile switching

---

## Alternatives Considered

### Alternative 1: Simpler Approach (Just LLM Profiles)
**Rejected because**:
- Doesn't support MCP per profile
- Users need complete environment switching, not just model switching
- Misses the opportunity to provide comprehensive cloud configurations

### Alternative 2: Keep MCP Separate from Profiles
**Rejected because**:
- Loses model-specific MCP optimization
- Harder to maintain consistency between model and MCP
- User has to manage two separate configurations

### Alternative 3: Cloud-Only Profiles (No Local Profiles)
**Rejected because**:
- Forces users to use cloud even if they have own API keys
- No offline capability
- Limits user customization

---

## Next Steps

1. **Review this design** with team
2. **Gather feedback** on:
   - MCP merge strategy (replace vs. merge)
   - Profile naming conventions
   - Sync frequency and triggers
3. **Create implementation plan** with timeline
4. **Build Phase 1** (core infrastructure)
5. **Test with users** before building Phase 2

---

## Questions for Discussion

1. **Should we support profile inheritance** (profiles that extend other profiles)?
   - Pro: DRY, easier maintenance
   - Con: More complexity

2. **Should cloud profiles be immutable** (cannot be edited, only copied)?
   - Pro: Clearer separation, prevents confusion
   - Con: Less flexible

3. **What happens to cloud profiles after cloud logout**?
   - Option A: Delete them
   - Option B: Keep them but mark as "disconnected"
   - **Recommendation**: Option B (keep but don't update)

4. **Should we cache verified models** to reduce API calls?
   - Yes, with TTL of 24 hours and manual sync option

---

## Conclusion

The proposed design provides:
- ✅ Automatic access to all verified OpenHands Cloud models
- ✅ Easy switching between models (single command or interactive)
- ✅ Integrated MCP configurations (cloud-provided + user customization)
- ✅ Profiles as complete agent configurations (LLM+MCP+more)
- ✅ Version-tracked synchronization
- ✅ Backward compatibility
- ✅ Extensible for future enhancements

This is significantly more robust than the naive approach while remaining user-friendly and maintainable.
