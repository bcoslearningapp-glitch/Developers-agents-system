# Setup

## Requirements

- Git
- Python 3.11 or later
- Claude Code, signed in
- Ollama 0.33 or compatible, with `gpt-oss:20b` and `gpt-oss:120b-cloud`
- OpenCode 1.18.29 or a compatible release
- Configured free-plan access for the approved Groq, Cloudflare Workers AI, OpenRouter, and Google models

Roo is not required by the current runtime. Ollama launches the implementation model through the restricted Claude Code harness; the other cloud providers use OpenCode.

## Verify this installation

Windows PowerShell:

```powershell
tools\agents\agentctl.cmd doctor --deep
tools\agents\agentctl.cmd test
tools\agents\agentctl.cmd status
```

macOS/Linux:

```bash
./tools/agents/agentctl doctor --deep
./tools/agents/agentctl test
./tools/agents/agentctl status
```

The doctor reports executable versions and model identifiers but never prints credential values.

## Existing project installation

Run the installer from the starter repository:

```powershell
tools\agents\agentctl.cmd init C:\path\to\existing-project
```

The target must already use Git. If it does not, inspect the project first and then explicitly use `--init-git`. The installer never commits and never overwrites an existing file. Conflicts are recorded in `agent/INSTALL_REPORT.md` for manual merging.

After installation:

1. Resolve any reported instruction/configuration conflicts.
2. Run `agentctl doctor --deep` and `agentctl test` inside the target.
3. Open Claude Code at the target root.
4. Ask Claude to run the codebase-audit workflow before changing an existing project.
5. Claude creates one atomic READY task and selects its worker profile.
6. The task lists exact, non-interactive verification commands in backticks for the project's stack.
7. Dispatch with `tools\agents\agentctl.cmd dispatch TASK-XXXX`.
8. Claude performs the final review after wrapper verification passes.

If previous Claude task, audit, or architecture documents are stored outside the project, archive only their safe top-level Markdown into indexed project memory:

```powershell
tools\agents\agentctl.cmd import-context "C:\path\to\historical-folder"
```

Potential credential-bearing Markdown is skipped and reported instead of copied.

## Safe operating rules

- Never put credentials in task files, prompts, reports, or repository configuration.
- Do not add a paid worker without explicit human approval.
- Do not run two dispatches concurrently.
- Do not manually move a task between lifecycle folders while a dispatch is running.
- Do not delete partial worker changes after failure; inspect the failure report and baseline first.
- Use `recheck` only for an environment-only verification failure, never to bypass a contract or code failure.

See `tools/agents/README.md` for detailed behavior and configuration.
