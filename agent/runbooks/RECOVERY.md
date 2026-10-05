# Recovery Runbook

If automation fails: preserve the worktree, inspect `agent/reports/qa/` and `.agent-worker/logs/`, reconcile task folder state, and resume from repository evidence. Never erase work to make state look clean.
