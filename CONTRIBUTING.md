# Contributing to OpenHands CLI

Thanks for helping improve OpenHands CLI.

OpenHands CLI is the standalone terminal interface for OpenHands. This repo owns the Textual TUI, the browser-served view behind `openhands web`, packaging for the standalone binary, and the CLI-specific workflows around those surfaces.

## Start with the shared OpenHands contribution guide

The shared OpenHands contribution guide is the source of truth for the overall contribution process and should stay up to date in the docs repo:

- Source of truth: https://github.com/OpenHands/docs/blob/main/overview/contributing.mdx

If a change belongs in the shared contributor guidance for all OpenHands repositories, update that docs page rather than duplicating the same detail here.

## What this repo adds on top

This file is intentionally short. It covers the repo-specific pointers contributors need before opening a PR here:

- OpenHands CLI is a Textual TUI project, so UI changes often need snapshot coverage in addition to normal pytest coverage.
- Some changes need validation against the packaged executable, not just the Python entrypoint.
- The detailed local setup, run loops, testing matrix, and packaging notes for this repo live in [Development.md](Development.md).

## Before you open a pull request

1. Read the shared OpenHands contributing guide above.
2. Follow [Development.md](Development.md) for local setup and validation commands.
3. Keep the PR focused and explain the user-visible effect of the change.
4. Run the relevant checks for the files you touched:
   - `make lint`
   - `make test`
   - `make test-snapshots` for TUI layout or rendering changes
   - `make test-binary` for binary, ACP, auth, packaging, or end-to-end CLI flows
5. If you changed the UI, include screenshots or snapshot updates so reviewers can see the result.

## Questions or discussion

- Open an issue in this repository for bugs or feature requests.
- Join the community on Slack: https://openhands.dev/joinslack

Thanks again for contributing.
