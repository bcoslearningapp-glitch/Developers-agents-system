# Project State

## Project
- Name: Kaizen — 30-Day Discipline Journal
- Purpose here: test project for the reusable agent system
- Application stack: React, TypeScript, Vite, Vitest; local-first browser storage

## Agent-system state
- Recovery copy created from the Downloads workspace; the original was not modified.
- Claude Code is the exclusive orchestrator, architect, task author/approver, and final reviewer.
- Approved free implementation workers are registered for Ollama and OpenCode.
- SMALL routes local-first to `gpt-oss:20b`; MEDIUM/HIGH use balanced cloud rotation.
- Usage observations, reserve thresholds, and provider cooldowns are stored locally under `.agent-worker/`.
- Wrapper-owned Git checks, report validation, and independent verification gate every dispatch.
- The prior TASK-0100 contract is archived as superseded because the recovery was completed outside the old, broken dispatcher.

## Live task state
- `TASK-0001` remains blocked from the earlier Kaizen test cycle. Its last recorded blocker was a Windows file lock on `esbuild.exe` during `npm ci`.
- No task is currently READY, active, or in review.

## Review status
The recovered runtime passes its local regression suite and syntax/configuration checks, but it has not yet received the user-required Claude Code final review. Do not represent Codex recovery work or implementation-worker self-reports as that review.

## Resume instruction
1. From a normal terminal, run `tools\agents\agentctl.cmd doctor --deep` and `tools\agents\agentctl.cmd test`.
2. Ask Claude Code to inspect the recovery diff and perform the final control-plane review without implementing production code.
3. If Claude passes the runtime, clear any stale Node/esbuild process before resuming `TASK-0001`.
4. Create or restore only one atomic READY task at a time, with exact non-interactive verification commands in its contract.

## Last verified update
- Date: 2026-09-07
- By: Codex recovery session (implementation and diagnostics only; not the required Claude final reviewer)
- Internal verification: Python compilation succeeded; 44 runtime tests passed before packaging.
