# Developer Agent Starter

A file-backed software-engineering agent system that keeps Claude Code in the control plane while delegating implementation to approved free-plan models.

## Role boundary

- Claude Code exclusively owns orchestration, architecture, task contracts, human decision requests, and final review.
- Ollama and OpenCode workers implement one approved atomic task at a time.
- Implementation workers cannot change product scope, architecture, agent governance, or decision records.
- Wrapper-owned Git checks and verification decide whether work is reviewable; model self-reports are never sufficient evidence.

## Approved workers

- Local Ollama `gpt-oss:20b` for SMALL tasks.
- Ollama Cloud `gpt-oss:120b-cloud`.
- Groq GPT-OSS 120B.
- Cloudflare Workers AI GPT-OSS 120B.
- OpenRouter Nemotron Ultra free endpoint.
- Google Gemini 3.8 Flash, including a HIGH-profile reasoning variant.

Only free-plan workers are permitted. Usage-aware rotation and provider cooldowns prevent one cloud allowance from being consumed before the others are used.

## Start here on Windows

```powershell
tools\agents\agentctl.cmd doctor --deep
tools\agents\agentctl.cmd test
tools\agents\agentctl.cmd status
```

Read `SETUP.md` for first-time setup and `tools/agents/README.md` for routing, security, recovery, and installation details.

The `agent/` directory is durable project memory. Chat history is helpful context but is never the source of truth.
