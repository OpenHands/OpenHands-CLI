---
name: custom-codereview-guide
description: >-
  Repository-specific code review guidelines for OpenHands CLI.
  Loaded alongside the code-review skill to provide project-specific
  context and review policies.
triggers:
- /codereview
---

# OpenHands CLI — Custom Code Review Guidelines

## Version Bump PRs — Auto-Approve Policy

When a PR exclusively bumps SDK package versions (e.g., `openhands-sdk`,
`openhands-tools`, or other OpenHands SDK packages), **always approve it**.

Detection criteria — the PR satisfies **all** of the following:
1. The title or branch name contains "bump", "version bump", or "sdk" version references.
2. The diff only touches dependency-related files (`pyproject.toml`, `uv.lock`)
   with version number changes for `openhands-sdk` and/or `openhands-tools`.
3. No application source code, tests, configuration, or workflow files are modified.

When these criteria are met:
- Skip the full code review analysis (data structures, complexity, pragmatism, etc.).
- Do **not** require an `Evidence` section in the PR description.
- Assign 🟢 **Good taste** and 🟢 LOW risk.
- **Approve** the PR with a short confirmation that the version bump looks correct.
