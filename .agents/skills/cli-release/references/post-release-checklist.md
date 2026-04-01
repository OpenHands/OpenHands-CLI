# Post-Release Checklist

After the GitHub release is published and the PyPI package is available,
several automated and manual follow-up steps are needed.

## Automated: Install Website Update

The `update-install-website.yml` workflow runs automatically when a
release is published. It creates a PR in the
[install-openhands-website](https://github.com/All-Hands-AI/install-openhands-website)
repository that updates the `VERSION` variable in `public/install.sh`.

```bash
gh pr list --repo All-Hands-AI/install-openhands-website \
  --search "update-version-<version>" --json number,title,url
```

Review and merge the PR. After merging, verify the install script serves
the new version:

```bash
curl -fsSL https://install.openhands.dev/install.sh | grep '^VERSION='
```

## Manual Verification

### Binary Assets

Confirm every expected platform binary is attached to the GitHub release:

```bash
gh release view <version> --repo OpenHands/OpenHands-CLI --json assets \
  --jq '.assets[] | "\(.name)  \(.size) bytes"'
```

Expected assets:
- `openhands-linux-x86_64`
- `openhands-linux-arm64`
- `openhands-macos-arm64`
- `openhands-macos-intel`

If any asset is missing, check the `cli-build-binary-and-optionally-release`
workflow runs for failures:

```bash
gh run list --repo OpenHands/OpenHands-CLI \
  --workflow "cli-build-binary-and-optionally-release.yml" --limit 5
```

### PyPI Package

Verify the `openhands` package is installable at the correct version:

```bash
pip install openhands==<version> --dry-run
```

Or check the PyPI API:

```bash
curl -s "https://pypi.org/pypi/openhands/<version>/json" | jq '.info.version'
```

## Troubleshooting

### PyPI Publication Failed

Re-run the `pypi-release.yml` workflow manually from the tag:

```bash
gh workflow run pypi-release.yml --repo OpenHands/OpenHands-CLI \
  --ref "<version>"
```

Alternatively, trigger via the GitHub Actions UI at
<https://github.com/OpenHands/OpenHands-CLI/actions/workflows/pypi-release.yml>.

### Binary Build Failed for a Platform

Individual platform builds run in a matrix. Re-run only the failed
jobs from the Actions UI, or re-trigger the entire workflow by
pushing the tag again (delete and recreate if necessary):

```bash
git tag -d <version>
git push origin :refs/tags/<version>
git tag <version>
git push origin --tags
```

> **⚠️ Warning**: Deleting and recreating tags should only be done
> before the release is published. After publication, prefer re-running
> the workflow instead.

### Install Website PR Not Created

If the automated PR did not appear, trigger the workflow manually:

```bash
gh workflow run update-install-website.yml \
  --repo OpenHands/OpenHands-CLI \
  -f version=<version>
```

### Install Website PR Has Conflicts

If the automated PR has merge conflicts, resolve them on the branch
or re-trigger the workflow with the version input:

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

### Snapshot Tests Fail on the Bump PR

The bump workflow automatically updates snapshot tests. If they still
fail, update them manually on the bump branch:

```bash
git checkout bump-version-<version>
uv sync --group dev
uv run pytest tests/snapshots/ --snapshot-update -v
git add tests/snapshots/
git commit -m "Update snapshot tests for <version>"
git push origin bump-version-<version>
```
