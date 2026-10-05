# Decision — DEC-0002 — Implementation worker model policy: primary + local fallback

## Status
Approved / in effect. 2026-09-06.

## Why this is recorded
`.claude/rules/00-orchestration.md` normal loop, `agent/quality/QUALITY_GATES.md`, and any future Orchestrator session (this one or a resumed one) need one durable place that says which model handles implementation, how a provider failure is treated, and what "smaller local model" does and does not excuse. This supersedes the ad hoc suggestion in chat (add a multi-cloud `ZOO_WORKER_MODELS` fallback chain) that the Orchestrator floated after TASK-0001 cycle 6's provider rate limit — the user instead verified a local model through the same harness and set this policy explicitly.

## What happened
TASK-0001 cycle 6 failed with an external Ollama provider `429` ("session usage limit") on `gpt-oss:120b-cloud`, not a task-contract or code defect (see `agent/history/CHANGELOG_AI.md`, cycle 6). Separately, the user has since verified `gpt-oss:20b` (a local model) end-to-end through the same Claude Code worker harness (`tools/agents/run_code_task.py`'s `ollama launch claude --settings .claude/worker-settings.json ...` invocation), including real Bash/`npm` execution — the same mechanism DEC-0001 established for the cloud model.

## Decision
1. **Primary implementation worker:** `gpt-oss:120b-cloud`.
2. **Local fallback worker:** `gpt-oss:20b` — verified working through the identical harness (worker-settings permissions, wrapper-owned independent re-verification, Allowed-paths enforcement all apply unchanged).
3. **A provider `429` / quota-exhaustion response is classified as an external provider failure, not an implementation failure.** It must not be scored, logged, or counted the same way as a genuine implementation defect (a real test failure, a contract violation, a fabricated report). Concretely: **a provider failure does not consume the task's implementation retry/rework-cycle budget** — it is not "rework cycle N+1," it is the same cycle re-attempted on different infrastructure once a worker actually runs.
4. **Do not blindly resend a large or loosely-bounded task unchanged to `gpt-oss:20b`.** A 20B local model has materially less headroom than a 120B cloud model for holding a large diff, a long rework history, and a wide acceptance-criteria list in context at once.
5. **On a primary-worker `429`, the Orchestrator's next action depends on the task's size:**
   - **Small, tightly bounded task** (a handful of Allowed paths, a short, concrete rework list, most acceptance criteria already independently confirmed correct in the working tree): may be redispatched **as-is** to `gpt-oss:20b`.
   - **Medium or large task:** split the *remaining* work into smaller atomic tasks sized for the local worker's context budget, **preserving already-correct work** — do not re-litigate or re-verify parts already confirmed correct by direct inspection or prior independent verification; scope each split task narrowly, the same way TASK-0001's own rework cycles have been narrowed cycle over cycle.
6. **The local worker is subject to every requirement the cloud worker is:** the same task contract discipline (Allowed paths, acceptance criteria, quality requirements, test/verification plan, security/privacy, out-of-scope), the same implementation-report schema, the same wrapper-owned independent re-verification (`typecheck`/`lint`/`format:check`/`build`/`test`/etc. — never trusting the worker's self-report), and the same independent Reviewer pass before a task can reach PASS.
7. **Quality gates are not weakened for the smaller model.** `agent/quality/QUALITY_GATES.md` applies identically regardless of which model executed the task; a `gpt-oss:20b` implementation cycle is reviewed exactly as strictly as a `gpt-oss:120b-cloud` one.

## Mechanical note (outside the Orchestrator's own write scope)
Actually routing a dispatch to a specific model is controlled by `tools/agents/run_code_task.py`'s `ZOO_WORKER_MODELS` environment variable (see `tools/agents/README.md`), which the Orchestrator's `./tools/agents/run-code-task TASK-XXXX` invocation reads from its process environment. The Orchestrator's Bash tool cannot itself set an environment variable inline (the shell guard only permits the bare approved-script invocation, no compound/prefixed commands) and cannot edit `tools/agents/**` (outside `agent/**`). In practice this means: **before the Orchestrator dispatches to the local fallback, `ZOO_WORKER_MODELS` needs to already be set appropriately in the environment the Bash tool inherits** (e.g. `gpt-oss:20b`, or `gpt-oss:120b-cloud,gpt-oss:20b` for automatic in-process fallback across both). This is noted here as an operational fact, not a request — the user already has the mechanism verified; the Orchestrator will follow whatever `ZOO_WORKER_MODELS` is set to at dispatch time and apply the size-based splitting judgment above around it.

## Alternatives considered
- **Multi-cloud fallback chain** (`glm-5.2:cloud`, `minimax-m2.7:cloud`, `gpt-oss:120b-cloud` — `tools/agents/README.md`'s documented default chain). Not the chosen path for now; the user verified a local model instead, which also removes dependence on a second/third cloud provider's own quota.
- **Always split into small tasks regardless of size**, to keep every dispatch uniformly small enough for the local model. Rejected as unnecessary overhead for the common case where the primary cloud worker is available and a task is naturally larger; splitting is reserved for the actual fallback scenario.
- **Treat provider 429s as ordinary implementation failures** (consuming rework-cycle count same as a code defect). Rejected — conflates an external, transient infrastructure condition with actual work quality, which would distort the task history and the Reviewer's picture of how many real correction cycles a task needed.

## Cost / payment impact
None new. `gpt-oss:20b` runs locally (no additional cloud spend); this is a resilience/continuity improvement, not a new vendor or cost.

## Security / privacy / confidentiality impact
None beyond what DEC-0001 already established: the local worker runs under the same `.claude/worker-settings.json` permission scope, the same Allowed-paths enforcement, and the same wrapper-owned verification. No new trust boundary is introduced by running the fallback locally rather than in the cloud — if anything, a local model reduces what leaves the machine.

## Consequence of postponing
N/A — already in effect per the user's instruction. Recorded here so a future session (or this one, resumed) has a durable answer instead of re-deriving the multi-cloud-fallback idea the Orchestrator floated in chat, which this policy supersedes.

## Approval requested / given
Given directly by the user in chat (2026-09-06): primary/fallback models named, 429-handling rule, size-based split-vs-redispatch rule, and the "no quality-gate weakening" constraint, all stated explicitly. No further approval needed; this record exists for durability, not to request sign-off.

## Related
- `agent/decisions/approved/DEC-0001-worker-npm-execution.md` — establishes the worker permission/verification harness this policy extends.
- `agent/history/CHANGELOG_AI.md` — TASK-0001 cycle 6 (the 429 that prompted this).
- `agent/tasks/ready/TASK-0001.md` (cycle 7) — currently paused, unaffected by this policy until the user says to redispatch (per their explicit instruction: no redispatch, no new cycle, no contract change from this alone).
- `tools/agents/README.md`, `tools/agents/run_code_task.py` — mechanical implementation of model selection (outside `agent/**`, not edited by this record).
