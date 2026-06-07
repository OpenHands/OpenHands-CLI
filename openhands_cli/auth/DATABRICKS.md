# Databricks sign-in (CLI)

The CLI can use a Databricks AI Gateway model (`databricks/<endpoint-name>`,
e.g. `databricks/databricks-claude-sonnet-4-5`). Configure it from the
**settings modal**: pick Databricks as the LLM provider, set the workspace host
and model, then choose an authentication method.

## Authentication methods

Selected via the `databricks_auth_method` field in the settings TUI:

| Method | What you provide |
|---|---|
| `pat` | A personal access token (`dapi...`) |
| `m2m` | Service-principal `client_id` + `client_secret` (client-credentials grant) |
| `u2m` | Interactive browser sign-in (OAuth Authorization Code + PKCE) |
| `profile` | A `~/.databrickscfg` profile name |

## U2M browser flow

`u2m` runs an inline browser login implemented in `databricks_pkce.py`
(`run_browser_pkce_flow`):

1. Generate a PKCE verifier/challenge and random `state`.
2. Start a local callback server at `http://localhost:<callback_port>/callback`
   (default port **8080**).
3. Open the system browser to the Databricks OIDC authorize URL.
4. Wait for the redirect back with `?code=`, then exchange the code for tokens.

The returned tokens (`access_token`, `refresh_token`, `expires_at`, `client_id`,
`host`) are stored and used for subsequent requests.

> The redirect URI registered in the Databricks account console **must match**
> `http://localhost:<callback_port>/callback` (default `http://localhost:8080/callback`).

## Shared with the SDK and web

The PKCE primitives (`generate_pkce`, `build_authorize_url`,
`exchange_code_for_tokens`) are imported from
`openhands.sdk.llm.providers.databricks.pkce` — a single source of truth shared
by the CLI, the web backend, and the SDK. The CLI only adds the local
browser/callback orchestration on top.

Turning settings into an LLM also goes through the SDK: settings are converted
to `create_llm(...)` kwargs by
`openhands.sdk.llm.providers.databricks.settings_bridge.kwargs_from_settings`,
the same path the OpenHands backend uses.
