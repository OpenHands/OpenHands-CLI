---
name: cli-release
description: >-
  This skill should be used when the user asks to "release the CLI",
  "prepare a CLI release", "publish a new CLI version", "cut a CLI release",
  "do a release", "bump the CLI version", or mentions the CLI release
  checklist or release process. Guides through the full OpenHands CLI
  release workflow from version bump to binary publication, emphasizing
  human checkpoints.
---

# CLI Release Guide

This skill walks through the OpenHands CLI release process step by step.

> **🚨 CRITICAL**: NEVER merge the release PR, create/push tags, or publish
> a GitHub release without the human's explicit approval. Release is the
> last line of human defense. Always present the current status and ask for
> confirmation before performing any irreversible action.

> **⚠️ Tag format**: This project uses tags **without** a `v` prefix
> (e.g., `1.13.0`, not `v1.13.0`).

## Phase 1: Trigger the Version Bump Workflow

Determine the target version (SemVer `X.Y.Z`). Then trigger the
`bump-version.yml` workflow, which creates a branch and draft PR
automatically.

### Via GitHub UI

Navigate to
<https://github.com/OpenHands/OpenHands-CLI/actions/workflows/bump-version.yml>,
click **Run workflow**, enter the version (e.g., `1.14.0`), and run it.

### Via GitHub API

```bash
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/OpenHands/OpenHands-CLI/actions/workflows/bump-version.yml/dispatches" \
  -d '{
    "ref": "main",
    "inputs": {
      "version": "<version>"
    }
  }'
```

The workflow will:
1. Validate version format (`X.Y.Z`)
2. Create branch `bump-version-<version>`
3. Update version in `pyproject.toml`
4. Regenerate `uv.lock`
5. Update snapshot tests (version appears in splash screen SVGs)
6. Open a draft PR titled **"Bump version to \<version\>"**

Once the workflow completes, retrieve the PR number for later phases:

```bash
gh pr list --repo OpenHands/OpenHands-CLI \
  --head "bump-version-<version>" --json number,title,url
```

## Phase 2: Wait for CI — Tests Must Pass

The bump PR triggers the standard CI suite. **All checks must pass.**

Monitor status:

```bash
gh pr checks <PR_NUMBER> --repo OpenHands/OpenHands-CLI
```

Key checks to verify:
- Lint
- Unit / integration tests
- Snapshot tests (updated by the bump workflow)
- Binary build

### ⏸ Checkpoint — Human Judgment on Failures

Decide with the team whether each failure is:
- **Blocking** — must fix before release
- **Known / pre-existing** — acceptable to release with a follow-up issue
- **Flaky** — re-run the workflow

Re-run failed jobs:

```bash
gh run list --repo OpenHands/OpenHands-CLI \
  --branch "bump-version-<version>" --limit 5

gh run rerun <RUN_ID> --repo OpenHands/OpenHands-CLI --failed
```

## Phase 3: Tag the Release

> **🚨 STOP — Do NOT tag without explicit human approval.**
> Present the CI status summary and ask the human to confirm.

Tag the latest commit on the version bump branch. **No `v` prefix.**

```bash
git fetch origin
git checkout bump-version-<version>
git tag <version>
git push origin --tags
```

Pushing the tag triggers two automated workflows:
- **`cli-build-binary-and-optionally-release.yml`** — builds platform
  binaries and creates a **draft** GitHub release with assets
- **`pypi-release.yml`** — builds and publishes the `openhands` package
  to PyPI

## Phase 4: Merge the PR

> **🚨 STOP — Do NOT merge without explicit human approval.**

Wait for CI to complete after tagging, then merge:

```bash
gh pr merge <PR_NUMBER> --repo OpenHands/OpenHands-CLI --merge
```

## Phase 5: Edit and Publish the GitHub Release

> **🚨 STOP — Do NOT publish without explicit human approval.**
> Publishing finalises the release for users.

Navigate to <https://github.com/OpenHands/OpenHands-CLI/releases> and
edit the draft release created by CI:

1. Click **Auto-generate release notes** (or write custom notes)
2. Review the notes
3. Click **Publish release**

### ⏸ Checkpoint — Verify Release Assets

After publishing, confirm all platform binaries were uploaded:

| Platform | Asset name |
|----------|-----------|
| Linux x86_64 | `openhands-linux-x86_64` |
| Linux ARM64 | `openhands-linux-arm64` |
| macOS Apple Silicon | `openhands-macos-arm64` |
| macOS Intel | `openhands-macos-intel` |

```bash
gh release view <version> --repo OpenHands/OpenHands-CLI --json assets \
  --jq '.assets[].name'
```

### ⏸ Checkpoint — Verify PyPI Publication

```bash
curl -s -o /dev/null -w "openhands: %{http_code}\n" \
  "https://pypi.org/pypi/openhands/<version>/json"
```

Should return `200`. Allow a few minutes for PyPI indexing.

## Phase 6: Update Install Website

After publishing the release, wait a couple of minutes. The
`update-install-website.yml` workflow automatically opens a PR in
[install-openhands-website](https://github.com/All-Hands-AI/install-openhands-website).

```bash
gh pr list --repo All-Hands-AI/install-openhands-website \
  --search "update-version-<version>" --json number,title,url
```

Approve and merge the PR so users get the latest version via:

```bash
curl -fsSL https://install.openhands.dev/install.sh | sh
```

If the automated PR was not created, trigger the workflow manually:

```bash
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/OpenHands/OpenHands-CLI/actions/workflows/update-install-website.yml/dispatches" \
  -d '{
    "ref": "main",
    "inputs": {
      "version": "<version>"
    }
  }'
```

## Phase 7: Post-Release — Notify the Team

Compose a Slack message for the human to post:

```
🚀 *CLI v<version> released!*

• PyPI: https://pypi.org/project/openhands/<version>/
• Release: https://github.com/OpenHands/OpenHands-CLI/releases/tag/<version>
• Install website PR: https://github.com/All-Hands-AI/install-openhands-website/pulls
```

See `references/post-release-checklist.md` for additional verification
steps and troubleshooting.

## Quick Reference — Full Checklist

- [ ] Trigger `bump-version.yml` with target version
- [ ] All CI checks pass on the bump PR
- [ ] **🚨 Get human approval**, then tag the release (no `v` prefix)
- [ ] **🚨 Get human approval**, then merge the PR
- [ ] **🚨 Get human approval**, then publish the GitHub release
- [ ] Verify platform binaries are attached to the release
- [ ] Verify `openhands` package is available on PyPI
- [ ] Approve and merge the install website PR
- [ ] Notify the team on Slack
