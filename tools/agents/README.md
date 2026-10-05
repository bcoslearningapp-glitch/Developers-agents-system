# Agent Worker Runtime

Claude Code is the only orchestrator, architect, and final reviewer. Implementation is delegated to approved free-plan workers through either Ollama or OpenCode.

## Windows quick start

```powershell
tools\agents\agentctl.cmd doctor --deep
tools\agents\agentctl.cmd test
tools\agents\agentctl.cmd status
tools\agents\agentctl.cmd dispatch TASK-0001
```

On macOS/Linux, use `./tools/agents/agentctl` instead.

## Commands

- `doctor [--deep]` checks Git, Python, Claude Code, Ollama, OpenCode, the free-worker registry, task contracts, and optionally the installed model IDs.
- `status` shows live task state and the currently calculated route for every profile.
- `route SMALL|MEDIUM|HIGH` previews worker ordering without launching a model.
- `validate TASK-XXXX` validates a READY task.
- `dispatch TASK-XXXX` runs exactly one READY implementation task.
- `recheck TASK-XXXX` re-runs wrapper-owned verification for a BLOCKED task without launching a worker.
- `test` runs the agent runtime regression suite.
- `init <project> [--init-git]` installs the system without overwriting existing project files.
- `import-context <directory>` archives safe top-level Markdown history under `agent/legacy-context/` and builds a selective-read index.

## Approved implementation workers

Only entries marked `free: true` in `worker_models.json` are accepted. The current approved set is:

- Ollama local `gpt-oss:20b`
- Ollama Cloud `gpt-oss:120b-cloud`
- Groq `groq/openai/gpt-oss-120b`
- Cloudflare Workers AI `cloudflare-workers-ai/@cf/openai/gpt-oss-120b`
- OpenRouter `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`
- Google `google/gemini-3.8-flash` (`--variant high` for its HIGH-profile entry)

Do not add a paid model or provider without an explicit human decision.

## Routing policy

Every task declares `SMALL`, `MEDIUM`, or `HIGH` under `## Worker profile`.

- SMALL is always local-first while local `gpt-oss:20b` is healthy.
- MEDIUM and HIGH use fair rotation among healthy free cloud providers.
- Usage pressure is calculated from locally observed request/token counts and optional configured provider limits.
- A provider enters cooldown after quota, access, connection, or temporary server failures.
- OpenRouter has a lower default scheduling weight and a larger reserve because its free endpoint is more rate-limit-sensitive.
- A failed implementation, missing report, test failure, scope violation, or wrapper failure stops the task. It never causes model hopping.
- MEDIUM/HIGH tasks never fall automatically to local 20B. Claude must split remaining work into SMALL tasks first.

Usage and cooldown state is stored in `.agent-worker/usage-ledger.json`; it contains counts and timestamps, never credentials.

Provider quotas are not uniformly discoverable. When `request_limit` and `token_limit` are `null`, the scheduler uses fair-share request rotation plus provider cooldown signals. Configure verified plan limits in `worker_models.json` if exact limits are known.

## OpenCode isolation

OpenCode is invoked in one-shot mode using its exact model ID:

```text
opencode.cmd run --model provider/model --format json --pure --agent build --dir PROJECT MESSAGE
```

For each attempt, the wrapper generates a restrictive permission configuration and passes it through `OPENCODE_CONFIG_CONTENT`, the runtime override layer. It:

- permits edits only in the task's Allowed paths and its implementation report;
- denies edits to agent governance, Claude/Roo rules, Git internals, and `.agent-worker/`;
- denies subagents, web access, external directories, and interactive questions;
- allows only exact, safety-checked commands declared in the task plus a narrow built-in Git/npm set;
- disables sharing, snapshots, and automatic updates for the worker process;
- enables only the selected provider.

The Git diff guard independently checks the result afterward. Tool permissions are prevention; the wrapper guard is verification.

## Verification across project types

Task contracts must put exact non-interactive verification commands in backticks under `## Test / verification plan`. The runtime recognizes bounded checks for Node package managers, Python, Rust, Go, .NET, Maven, Gradle, and Make. It independently re-runs each accepted command exactly once after the worker exits. It never adds undeclared package scripts; Claude decides which checks are relevant when it authors the task contract.

Shell composition/redirection, dev servers, watchers, deploy/publish/release scripts, and destructive Git commands are refused. An application task with no safe runnable verification command fails closed. This keeps installation portable without turning the task file into unrestricted shell access.

## Failure and recovery

Before a worker starts, the wrapper stores a unique Git dirty-state baseline under `.agent-worker/state/`. It compares the final state with that exact baseline, so unrelated pre-existing changes are not attributed to the worker.

On failure, partial work is preserved and the task moves to `blocked/`. On an environment-only verification failure, `recheck` loads the persisted baseline, repeats all contract and verification checks, and moves the task to `review/` only on a genuine pass.

Only provider/access failures are fallback-eligible:

- quota or rate limit;
- authentication/access rejection;
- temporary provider/server/connection failure;
- missing worker executable.

Worker timeouts are treated as implementation failures because a timed-out session may have already changed files.

## Environment overrides

- `OLLAMA_BIN`: Ollama executable path.
- `OPENCODE_BIN`: OpenCode executable path.
- `ZOO_WORKER_MODELS`: manual Ollama-only model chain; bypasses profile routing.
- `ZOO_WORKER_TIMEOUT_SECONDS`: worker timeout, default 3600.
- `ZOO_VERIFY_TIMEOUT_SECONDS`: per project verification command timeout, default 600.

## Installing into an existing project

From this source repository:

```powershell
tools\agents\agentctl.cmd init C:\path\to\existing-project
```

The installer requires Git unless `--init-git` is explicitly supplied. It copies only the generic runtime and blank project-memory structure, never Kaizen content. Existing files are preserved and listed as conflicts in `agent/INSTALL_REPORT.md`; they must be reviewed and merged before autonomous dispatch.

If earlier AI specifications or audit notes live outside the Git project, import them without placing everything in Claude's active context:

```powershell
tools\agents\agentctl.cmd import-context "C:\path\to\historical-folder"
```

Only top-level Markdown is considered. `.env`, cookies, logs, HTML, caches, and other files are ignored. Markdown containing credential-like assignments is skipped and listed for manual review. Claude reads `agent/legacy-context/IMPORT_INDEX.md` first, then opens only the documents relevant to the current audit or task.
