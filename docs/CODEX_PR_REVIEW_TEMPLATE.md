# Dental PMS Codex PR Review Template

## Purpose

This template preserves the standard Dental PMS PR review and merge workflow so future sessions can follow the same review-first, continuity-aware process without relying on chat history.

## Current continuity assumptions

As of `master@4bb2238`:

- PR `#347` is merged and verified.
- The patient-note bridge into centralized `/notes` is complete.
- Note taxonomy remains exactly two types only:
  - `clinical`
  - `admin`
- Patient note edit/archive remains centralized on `/notes`.
- R4 is strictly read-only and must not be touched unless explicitly overridden.
- The repo default branch for post-merge sync is `master`.
- `gh pr review --approve` may be rejected for self-authored PRs; that is non-blocking if the review is otherwise clean and checks are satisfactory.

## Reusable prompt

```text
You are working on the Dental PMS project.

Operate carefully, keep scope tight, and preserve project continuity. Before doing anything, read the current repo state and recent continuity notes so your work matches the existing project decisions.

Core rules
- Review first, merge second.
- Do not broaden scope.
- Do not change code unless I explicitly ask for code changes.
- If I ask for PR review/merge, treat that as read/review/merge only.
- R4 is strictly read-only. Do not touch or modify R4 in any way unless I explicitly override that rule.
- Respect established product decisions recorded in docs/STATUS.md and related continuity docs.
- If anything is unexpectedly different from the reported slice, stop and report instead of merging.
- If there are conflicts, missing commits, unexpected files, failing checks, or scope drift, stop and report clearly.
- Use the repo default branch for post-merge sync. In this repo, that branch is currently master.
- If gh pr review --approve is rejected because the authenticated account authored the PR, treat that as non-blocking. Record it clearly, then continue only if the review is otherwise clean and checks are satisfactory.

Standard task
Please perform the normal Dental PMS PR review workflow for the PR I specify, then merge only if everything is still clean.

Inputs
- Repo path: /home/amir/dental-pms
- PR number: <PR_NUMBER>
- Expected branch: <BRANCH_NAME>
- Expected head SHA: <HEAD_SHA>
- Optional expected changed files:
  - <FILE_1>
  - <FILE_2>
  - <FILE_3>
  - <FILE_4>

Required workflow
1. Move to the repo and inspect current state.
2. Read the relevant continuity context before reviewing:
   - docs/STATUS.md
   - AGENTS.md
   - any obviously relevant decision/runbook doc if the PR touches that area
3. Confirm local branch, SHA, and working tree status.
4. Inspect the PR metadata and exact diff.
5. Confirm the changed files match the intended slice.
6. Review for:
   - scope coherence
   - product-decision alignment
   - regression risk
   - accidental unrelated edits
   - tests/checks relevant to the slice
7. If clean, submit approval if possible, then merge the PR.
8. After merge:
   - update local master
   - confirm new local master SHA
   - run post-merge verification
   - report whether any deploy step is needed
9. Explicitly confirm R4 remained untouched.

Commands/workflow to use
- cd /home/amir/dental-pms
- git status --short --branch
- git branch --show-current
- git rev-parse --short HEAD
- gh pr view <PR_NUMBER> --repo Minnerman/dental-pms
- gh pr diff <PR_NUMBER> --repo Minnerman/dental-pms
- compare diff contents with the expected changed files
- if needed, inspect per-file diffs only for the touched files
- if the review is clean, try to submit approval review on the PR
- if self-approval is rejected because the same account authored the PR, record that and continue
- merge the PR if still clean
- git checkout master
- git pull --ff-only
- git rev-parse --short HEAD
- docker compose exec -T backend pytest -q
- ./ops/health.sh
- ./ops/verify.sh

Decision rules
- If the PR matches the intended slice and checks are satisfactory, merge it.
- If the diff includes unexpected files, hidden scope creep, or anything inconsistent with continuity notes, stop and report.
- Do not "fix while here".
- Do not open a follow-up coding slice unless I explicitly ask.

Output format
Reply in this exact structure:

1. Pre-merge review
- Current branch:
- Current SHA:
- Working tree:
- PR state:
- Expected scope:
- Actual changed files:
- Scope match: Yes/No
- Review findings:
- Approval attempted: Yes/No
- Approval submitted: Yes/No
- If not submitted, reason:

2. Merge
- PR merged: Yes/No
- Merge commit SHA:
- Notes:

3. Post-merge local sync
- Local master updated: Yes/No
- New local master SHA:

4. Verification
- docker compose exec -T backend pytest -q:
- ./ops/health.sh:
- ./ops/verify.sh:
- Deploy needed: Yes/No
- Reason:

5. Guardrails
- R4 untouched: Yes/No
- Any blockers or follow-up notes:

If you stop without merging, explain exactly why and what differs from expectation.
```

## Example

```text
PR number: 347
Expected branch: stage163h-chunk13-patient-note-open-in-notes
Expected head SHA: 129d247
Optional expected changed files:
- frontend/app/(app)/patients/[id]/PatientDetailClient.tsx
- frontend/app/(app)/notes/page.tsx
- frontend/tests/patient-notes.spec.ts
- docs/STATUS.md
```
