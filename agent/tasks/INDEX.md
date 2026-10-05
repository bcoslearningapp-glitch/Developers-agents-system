# Task Index

Folder location is the canonical task status.

| Task | Title | Milestone | Folder/Status | Latest review | Notes |
|---|---|---|---|---|---|
| TASK-0001 | Project scaffold and toolchain (Vite + React + TypeScript + Vitest) | M1 | blocked/BLOCKED (cycle 10, environment) | R1: CHANGES_REQUIRED (`agent/reports/review/TASK-0001-R1.md`) | Cycles 1–7: governance/fabrication/dependency/artifact/permission issues, all fixed. Cycle 8: `typecheck`/`lint`/`format:check`/`test`/`build` all genuinely passed at once, independently confirmed — but hung ~1hr on a contract-wording bug (preview server re-verification). Cycle 9 fixed that plus a duplicate-test issue but introduced two new regressions (still contained the trigger phrase; a Vitest `exclude` override that deleted the default `node_modules/**` exclusion). **Cycle 10 fixed both correctly** (confirmed by direct inspection: targeted type cast restored, `include` allow-list in place, 5 files genuinely reformatted) **but hit a recurring `npm ci` EPERM** unlinking `esbuild.exe` — a Windows file-lock, almost certainly an orphaned process from an earlier manually-terminated dispatch, not a code or contract defect. **Stopped per instruction: this needs the user to clear the lock, not another rework cycle.** `agent/tasks/blocked/TASK-0001.md` holds the exact, still-valid cycle-10 contract — restore it to `ready/` unchanged once the environment is clear. |
| TASK-0002 | Domain model types and calendar-date module | M1 | outline only (not yet a task file) | — | Depends on TASK-0001. Pure `src/domain/**`: entity types, 6 indicators, 5 day types, phases, `YYYY-MM-DD` date arithmetic. |
| TASK-0003 | Versioned local storage engine | M1 | outline only (not yet a task file) | — | Depends on TASK-0002. Storage adapter, envelope, validation, migrations, corruption quarantine. |
| TASK-0004 | Journal repository and React state provider | M1 | outline only (not yet a task file) | — | Depends on TASK-0003. Single write path + `JournalProvider`; covers the reload-persistence M1 exit criterion. |
| TASK-0005 | App shell, hash router, and base design tokens | M1 | outline only (not yet a task file) | — | Depends on TASK-0004. `#/today|progress|plan|weekly|history` routing, responsive shell, minimal tokens. |
| TASK-0006 | Five view destinations with empty states | M1 | outline only (not yet a task file) | — | Depends on TASK-0005. Closes M1: Today/Progress/Plan/Weekly/History reachable with proper empty states. |

Full architecture and per-task rationale: `agent/architecture/ARCHITECTURE.md`, `agent/architecture/decisions/ADR-0001-tech-stack.md`. TASK-0002–0006 will be written as full contracts (using `agent/templates/TASK.md`) and moved to `ready/` one at a time as each predecessor completes review.

## Infra track (tooling/agent-workflow, not part of the Kaizen product milestones)

Task IDs `0100+` are reserved for `tools/agents/**` infrastructure work so they never collide with the product task sequence above.

| Task | Title | Worker profile | Folder/Status | Latest review | Notes |
|---|---|---|---|---|---|
| TASK-0100 | Provider-agnostic implementation-worker fallback router (Ollama + OpenCode: OpenRouter/Groq/Cloudflare/Google) | HIGH | archive/superseded | Required | The old oversized contract and failed cycles are preserved under `agent/tasks/archive/`. Recovery implementation now exists in the working copy and must receive Claude Code final review before live use. |
