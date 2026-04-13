---
name: verify
description: >-
  Orchestrate repo-level verification of a PR by pushing changes, then polling
  CI checks, PR review, and QA workflows until all pass — or until issues are
  found that need fixing. The agent reads feedback, fixes code, pushes again,
  and repeats. Uses only standard `gh` CLI commands that work on any GitHub repo.
triggers:
- /verify
---

# /verify — Repo-Level Verification via Polling

Orchestrate the push → poll → fix → push loop for a pull request.
You poll the repo's verifiers with `gh` CLI, read feedback, fix issues, and iterate.
No scripts — you are the orchestration loop.

Requires: `gh` CLI authenticated with repo access, a PR branch.

## Discover what the repo has

Not every repo has all three verification layers. Before entering the loop,
check which ones exist. Only poll layers that are actually set up.

```bash
gh workflow list --json name --jq '.[].name'
```

- **CI checks** — almost every repo has these. If `gh pr checks` returns results, CI is present.
- **PR review bot** — look for a workflow named like "PR Review" or "pr-review" in the output above, or check for `.github/workflows/pr-review*.yml` in the repo. If it's not there, the repo doesn't have automated PR review. Skip step 3 entirely.
- **QA bot** — look for a workflow named like "QA" or "qa-changes". If it's not there, the repo doesn't have automated QA. Skip step 4 entirely.

A repo might have only CI. Or CI + review. Or all three. Your "all passed"
condition is: every *present* layer is green. Don't block waiting for layers
that don't exist.

## The loop

1. Push and ensure PR exists.
2. Poll each present verification layer.
3. Decide: all passed? fix needed? wait?
4. If fix needed — fix, commit, push, re-request review from bots, go to 2.
5. If waiting — sleep 30-60s, go to 2.
6. If all present layers passed on the *current* SHA — done.

IMPORTANT: pushing a fix is NOT the end. After every fix+push you MUST
re-request review from the review bot (if present) and go back to step 2.
The loop only ends when the verifiers pass on your latest SHA. Addressing
feedback and pushing a commit is just one iteration — the bot needs to
review the new code too.

## Step 1 — Push and ensure PR exists

```bash
git push origin HEAD
gh pr create --fill 2>/dev/null || true
gh pr view --json number,url,headRefOid --jq '"\(.number) \(.url) \(.headRefOid)"'
```

## Step 2 — Poll CI checks

```bash
gh pr checks --json name,state,bucket --jq '
  { passed:  [.[] | select(.bucket=="pass")]  | length,
    failed:  [.[] | select(.bucket=="fail")]  | length,
    pending: [.[] | select(.bucket=="pending")] | length }'
```

- Zero failed, zero pending → CI green.
- Any pending → wait and re-poll.
- Any failed → diagnose (see "CI failure classification" below).

To inspect a failure:

```bash
SHA=$(gh pr view --json headRefOid --jq .headRefOid)
gh run list --commit "$SHA" --status failure --json databaseId,name,conclusion \
  --jq '.[] | "\(.databaseId)\t\(.name)\t\(.conclusion)"'
gh run view <run-id> --log-failed
```

## Step 3 — Poll PR review (if present)

Skip this step if the repo has no review bot.

```bash
gh pr view --json reviews --jq '
  [.reviews[] | select(
    .authorAssociation == "OWNER" or
    .authorAssociation == "MEMBER" or
    .authorAssociation == "COLLABORATOR" or
    (.author.login | test("openhands|all-hands-bot"; "i"))
  )] | last | { state: .state, reviewer: .author.login, body: .body[0:300] }'
```

- `APPROVED` → review passed.
- `CHANGES_REQUESTED` → read the body and inline comments, fix code.
- `COMMENTED` → may have actionable suggestions; read and decide.
- No matching review yet → bot may still be running; wait and re-poll.

Inline review comments (when changes requested):

```bash
gh api "repos/{owner}/{repo}/pulls/{number}/comments" \
  --jq '.[] | select(.user.login | test("openhands|all-hands-bot"; "i"))
        | { path: .path, line: .line, body: .body[0:200] }'
```

## Step 4 — Poll QA report (if present)

Skip this step if the repo has no QA bot.

QA reports are PR issue comments with a status line like `Status: PASS`.

```bash
gh api "repos/{owner}/{repo}/issues/{number}/comments" --paginate \
  --jq '[.[] | select(
    (.user.login | test("openhands|all-hands-bot"; "i")) and
    (.body | test("Status:\\s*(PASS|FAIL|PARTIAL)"; "i"))
  )] | last | { author: .user.login, body: .body[0:500], url: .html_url }'
```

- `PASS` → QA passed.
- `FAIL` → read details, fix code.
- `PARTIAL` → some passed, some failed; read details.
- No QA comment yet → bot may still be running; wait and re-poll.

## Step 5 — Decide and act

For each present layer, check its status. If a layer is not present in the
repo, treat it as passing.

- All present layers green on current SHA → done.
- CI failed → fix code, or rerun if flaky (see below).
- Review requested changes → read comments, fix, push.
- QA failed/partial → read report, fix, push.
- Anything still pending → sleep 30-60s, re-poll.
- PR closed/merged → stop.

After fixing, commit, push, AND re-request review:

```bash
git add -A
git commit -m "fix: address <CI failure | review feedback | QA failure>"
git push origin HEAD

# Re-request review from the bot so it reviews the new SHA:
gh pr comment --body "Addressed feedback in $(git rev-parse --short HEAD). Ready for another look."
gh api -X POST "repos/{owner}/{repo}/pulls/{number}/requested_reviewers" \
  -f 'reviewers[]=all-hands-bot'
```

Then go back to step 2. You are not done until the bot reviews the new
SHA and all present layers pass.

## CI failure classification

Branch-related (fix the code):
- Compile/lint/typecheck failures in files you touched
- Deterministic test failures in changed areas
- Snapshot or static-analysis violations from your changes

Flaky / unrelated (rerun the jobs):
- Network/DNS/registry timeouts
- Runner provisioning or startup failures
- GitHub Actions infrastructure errors
- Non-deterministic failures in code you didn't touch

Rerun: `gh run rerun <run-id> --failed`

Retry budget: at most 3 reruns per SHA. After that, treat as real.

## Stop conditions

Stop ONLY when:
- All present verification layers passed on the current SHA.
- PR closed or merged (`gh pr view --json state --jq .state`).
- Retry budget exhausted — CI still failing after 3 reruns of the same SHA.
- Blocked on something requiring user input.

NOT a stop condition:
- You pushed a fix commit. That's just one iteration — re-request review and keep going.
- You replied to review comments. The bot still needs to review the new code.
- CI is green but review bot hasn't re-reviewed your fix yet. Wait for it.

Keep going when:
- Checks still pending.
- Bots haven't posted yet (few minutes after push).
- Just pushed a fix and CI hasn't started.

## Polling cadence

- CI pending/failing: every 30-60s.
- CI green: back off (60s, 2m, 4m), reset on any state change.
- Just pushed a fix: re-poll immediately.

## vs babysit-pr

`/verify` is an active orchestrator — you write code, push, poll, fix, repeat.
`/babysit-pr` is a passive monitor — watches someone else's PR via a Python script.
Use `/verify` when you're the coding agent. Use `/babysit-pr` when you just need to watch.

## References

- Verification signal details: `references/workflow-signals.md`
- CI failure heuristics: same as `babysit-pr/references/heuristics.md`
