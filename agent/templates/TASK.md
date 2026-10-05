# TASK-XXXX — <Title>

## Status
READY

## Milestone
M-X

## Worker profile
Exactly one of `SMALL`, `MEDIUM`, or `HIGH`. Use SMALL for a narrow, low-risk edit suitable for the local 20B worker; MEDIUM for ordinary multi-file implementation; HIGH for security-sensitive, migration-heavy, or complex cross-cutting work. Classify the actual remaining work, not the task's original scope.

## Goal
One bounded outcome.

## Requirement sources
- `FR-XXX` — `agent/product/PRD.md#...`
- Architecture: `agent/architecture/...`
- Design: `DES-XXX` if applicable
- Approved decision: `agent/decisions/approved/...` if applicable

## Preconditions / dependencies
- None / exact dependencies

## Allowed paths
Replace these examples with the exact production/config/test paths the worker may modify. Glob patterns are allowed.
- `REPLACE_WITH_EXACT_PATH/**`

## Forbidden changes
- Anything not listed in Allowed paths
- Product scope/behavior beyond this contract
- Architecture/decision/task-management documents
- Production deployment, push, merge, or commit

## Acceptance criteria
- [ ] AC-1 ...
- [ ] AC-2 ...

## Quality requirements
List applicable gates from `agent/quality/QUALITY_GATES.md`.

## Test / verification plan
List exact non-interactive commands in backticks, for example `python -m pytest -q`, `npm run test`, or `cargo test --locked`. The wrapper independently re-runs safe declared checks. Never use a dev server, watcher, deploy, publish, release, destructive Git command, shell pipeline, or redirected/compound command here.

## Security / privacy
State relevant constraints. Write `No special impact identified` only after considering it.

## Accessibility / usability
State relevant constraints for user-facing work.

## Out of scope
- ...

## Rework requirements
None. Reviewer/Orchestrator appends bounded corrections here for another implementation cycle.

## Decision gate
- `NONE`
