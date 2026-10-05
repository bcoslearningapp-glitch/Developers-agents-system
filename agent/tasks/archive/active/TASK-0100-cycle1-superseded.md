# TASK-0100 — SUPERSEDED

This `active/` copy is stale. The wrapper process that placed it here (rework cycle 1's dispatch) exited with an unhandled error (code 1) before it could move the task to either `review/` or `blocked/` on its own — see `agent/tasks/blocked/TASK-0100.md`'s `## Rework requirements` → "Rework cycle 2 (pending)" for the confirmed findings (a safety-critical Allowed-path violation-detection regression, a self-report/wrapper-verification contradiction on unit tests, and this unclean crash itself).

The live, current record is `agent/tasks/blocked/TASK-0100.md`. No worker should be dispatched from this file.
