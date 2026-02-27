# Release Procedure

This document outlines the steps to release a new version of OpenHands CLI.

## Steps

### 1. Trigger Version Bump

Go to GitHub Actions and manually trigger the **"Bump Version"** workflow with the new version number.

- Navigate to: [Actions → Bump Version](https://github.com/OpenHands/OpenHands-CLI/actions/workflows/bump-version.yml)
- Click "Run workflow"
- Enter the new version number (e.g., `1.13.0`)
- Click "Run workflow"

### 2. Wait for CI

Wait for the CI workflow to finish. It will automatically:
- Update the version in `pyproject.toml`
- Regenerate `uv.lock`
- Update snapshot tests
- Open a draft PR

### 3. Verify the PR

- Review the changes in the PR
- Ensure all CI tests are passing
- Verify the version was updated correctly

### 4. Tag the Release

Tag the latest commit on the PR branch with the version number.

**Using command line:**
```bash
git tag <version>
git push origin --tags
```

**Using GitHub Desktop:**
1. Checkout to the release branch
2. Click the "History" tab
3. Right-click the latest commit
4. Click "Create tag"
5. Enter the release version (e.g., `v1.13.0`)
6. Push changes

### 5. Merge the PR

- Wait for CI to complete after tagging
- Approve the PR
- Merge it to main

### 6. Edit the Release

Visit the OpenHands CLI releases page:
- https://github.com/OpenHands/OpenHands-CLI/releases

Edit the draft release:
- Add release notes
- Publish as latest release

### 7. Update Install Website

Wait a couple of minutes after publishing the release. A PR should automatically be opened in the install website repository:
- https://github.com/All-Hands-AI/install-openhands-website/pulls

Approve and merge the latest pull request to update the installation instructions.
