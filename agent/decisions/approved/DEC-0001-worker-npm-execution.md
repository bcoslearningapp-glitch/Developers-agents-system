# Decision — DEC-0001 — Give the implementation worker real `npm` execution, without loosening the Orchestrator's permission boundary

## Status
Resolved / approved. 2026-09-06.

## Why this needed the user
Security/permission policy for the Claude Code control-plane boundary (`.claude/settings.json`'s allowlist is explicitly documented in `SETUP.md` §4 as "the Claude Code safety boundary"). Also mechanical: neither the Orchestrator's tools (`guard_claude_writes.py` restricts Write/Edit to `agent/**`) nor the implementation worker's tools can edit anything outside `agent/**`/task Allowed paths, so only a human could make this change.

## What was proposed vs. what was actually implemented
The Orchestrator's original recommendation (see history below) was to add eight narrow `Bash(npm ...)` allow patterns directly to the shared, paid-Orchestrator `.claude/settings.json`. **That is not what was implemented, and it is no longer necessary.** The user instead:

- Created a **separate** `.claude/worker-settings.json`, scoped only to the implementation worker's Ollama-backed Claude Code session, with a narrow `permissions.allow` list for exactly the `npm` commands the worker needs (`install`, `ci`, `run build`, `run test`, `run lint`, `run typecheck`, `run check`, `run format:check`).
- Updated `tools/agents/run_code_task.py` to launch the worker with `--settings .claude/worker-settings.json` and an explicit `--tools Bash,Edit,Read,Write,Glob,Grep` allowlist, so the paid Orchestrator's own `.claude/settings.json` (and its hooks) is never touched, loosened, or shared with the worker session.
- Added wrapper-owned **independent verification**: after the worker claims success, `run_code_task.py` now runs the project's standard npm scripts itself (`typecheck`, `lint`, `test`, `build`, `check`, `format:check`, plus anything the task's verification plan names explicitly) and treats any failure as BLOCKED, regardless of what the worker's own implementation report claims.
- Confirmed empirically that `npm run build` now actually executes inside the worker's session.

## Decision
Adopt the user's implemented approach in place of the originally recommended option:
1. Worker-only `.claude/worker-settings.json` grants the narrow `npm` Bash permissions.
2. The shared `.claude/settings.json` governing the Orchestrator's own session is untouched — its allowlist, deny list, and `PreToolUse` hooks (`guard_claude_writes.py`, `guard_claude_bash.py`) still apply only to the Orchestrator.
3. Implementation reports are no longer trusted as proof of a passing command; the wrapper re-runs the real verification scripts itself and BLOCKS on any independently-observed failure.

## Alternatives (as originally presented)
- **Option A** (originally recommended): add the same npm allow patterns to the shared `.claude/settings.json`. Superseded — unnecessary now that a worker-only settings file exists, and strictly worse (it would have widened what the Orchestrator's own session could theoretically run, however narrowly scoped).
- **Option B**: broad `Bash(npm *)` allowlist. Not adopted; the implemented list stays script-scoped.
- **Option C**: no permission change, fully manual implementation. Not adopted; defeats the autonomous-worker workflow.

## Cost / payment impact
None. No new service, vendor, or spend.

## Security / privacy / confidentiality impact
Net **improvement** over the originally-recommended option: the paid Orchestrator's own permission surface is unchanged (still cannot run arbitrary Bash, still restricted to `agent/**` writes), and the worker's elevated `npm` access is now both (a) isolated to a settings file the worker alone uses, and (b) backstopped by wrapper-owned re-verification that no longer trusts the worker's self-reported results — directly closing the fabrication failure mode observed in TASK-0001 cycle 2 (see `agent/reports/review/TASK-0001-R1.md`).

## Consequence of postponing
N/A — already resolved. TASK-0001 rework cycle 3 can proceed.

## Approval requested / given
Approved by the user in chat (2026-09-06): "The worker infrastructure problem has been fixed externally... Therefore DEC-0001's proposed change to the Orchestrator `.claude/settings.json` is no longer required." Superseded pending entry removed from `agent/decisions/PENDING.md`.

## Related
- `agent/decisions/PENDING.md` (former pending entry, now resolved and removed).
- `agent/reports/review/TASK-0001-R1.md` (the review that surfaced the root cause).
- `tools/agents/run_code_task.py`, `.claude/worker-settings.json` (the actual implementation of this decision — tool-specific, outside `agent/**`, changed directly by the user/another agent, not by the Orchestrator).
- `agent/tasks/ready/TASK-0001.md` (rework cycle 3, now unblocked by this decision).
