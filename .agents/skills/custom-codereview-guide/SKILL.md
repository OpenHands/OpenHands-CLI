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

## Dependency release-age review

For dependency additions or updates, inspect every changed third-party npm or
PyPI version, including transitive lockfile changes. Require at least seven days
since publication of that exact version. Use registry publication/upload metadata
or the relevant artifact's `uv.lock` `upload-time`; a weekly bot schedule, an old
package name, or a passing install is not age evidence.

For an under-seven-day artifact, leave a COMMENT naming the package, version,
publication time, and source, and defer approval until it ages out or a maintainer
explicitly approves a narrowly documented exception. If publication time is
unavailable, ask for that evidence. Existing named first-party exemptions apply
only to those packages, not their third-party dependencies or blanket approval
of the lockfile. Apply this check before any dependency-bump fast path.

Flag removal or weakening of seven-day uv/Dependabot guards or new broad
exemptions. Dependabot security updates bypass cooldown, so review them under
the explicit maintainer-exception rule in `AGENTS.md`; agents cannot approve
their own bypass.

## Version Bump PRs — Auto-Approve Policy

When a PR exclusively bumps SDK package versions (e.g., `openhands-sdk`,
`openhands-tools`, or other OpenHands SDK packages), **always approve it**
by submitting an actual GitHub approval review via the API.

Detection criteria — the PR satisfies **all** of the following:
1. The title or branch name contains "bump", "version bump", or "sdk" version references.
2. The diff only touches dependency-related files (`pyproject.toml`, `uv.lock`)
   with version number changes for `openhands-sdk` and/or `openhands-tools`.
3. No application source code, tests, configuration, or workflow files are modified.

First apply the dependency release-age review above to any changed third-party
artifacts. The first-party SDK exemption does not exempt transitive dependencies.

When these criteria are met and that check passes:
- Skip the full code review analysis (data structures, complexity, pragmatism, etc.).
- Do **not** require an `Evidence` section in the PR description.
- Assign 🟢 **Good taste** and 🟢 LOW risk.
- **Submit an APPROVE review via the GitHub API** (not just a comment). Use:
  ```bash
  gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews \
    -f event="APPROVE" \
    -f body="✅ SDK version bump looks correct. Auto-approved."
  ```
  Do NOT merely comment that the PR is "approved" or "ready to merge" — you
  MUST use the GitHub Pull Request Reviews API with `event: "APPROVE"` so the
  PR actually receives a green approval checkmark.
