# TASK-0100 — SUPERSEDED

Rework cycle 2's fully-drafted contract now lives at `agent/tasks/ready/TASK-0100.md` (validated, not yet dispatched — awaiting approval). This `blocked/` copy is stale.

## Why cycle 2 exists
Rework cycle 1's dispatch (`gpt-oss:120b-cloud`, exit 0, report claimed `Status: COMPLETED`) was found, on forensic inspection, to have removed the wrapper's core Allowed-path/governance violation-detection logic entirely, to have a `--recheck` implementation whose own change-detection is broken (always resolves to `MIXED`), a self-report vs. wrapper-verification contradiction on unit-test results, and an unclean exit-code-1 crash. See `agent/tasks/ready/TASK-0100.md`'s `## Rework requirements` → "Rework cycle 2" for the full findings and the required recovery design (centralized violation-detection helper; persisted pre-dispatch baseline used by both normal dispatch and `--recheck`; fail-closed on a missing/malformed baseline; visible, non-swallowed unexpected-exception handling; regression tests).

No worker should be dispatched from this file.
