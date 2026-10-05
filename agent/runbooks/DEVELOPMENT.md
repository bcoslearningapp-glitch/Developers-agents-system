# Development Runbook

Document project-specific install, run, build, seed, and developer environment commands after architecture is established.

## Kaizen — local development

Stack: React 19 + TypeScript (strict) + Vite 7, no backend. See `agent/architecture/STACK.md` and `agent/architecture/decisions/ADR-0001-tech-stack.md` for rationale.

### Prerequisites
- Node.js `>=20.19` (see `.nvmrc` at the repo root once TASK-0001 lands).
- npm (bundled with Node).

### Install
```
npm ci
```
Use `npm ci` (not `npm install`) once `package-lock.json` exists, for a reproducible install.

### Scripts
| Script | What it does | When to run it |
|---|---|---|
| `npm run dev` | Starts the Vite dev server with hot reload. | While developing locally. |
| `npm run build` | Type-checks and produces a production bundle in `dist/`. | Before verifying a build, before release. |
| `npm run preview` | Serves the built `dist/` bundle locally. | To sanity-check a production build. |
| `npm run typecheck` | Runs `tsc --noEmit`. | Part of every task's verification; CI-equivalent gate. |
| `npm run lint` | Runs ESLint (flat config), zero warnings tolerated. | Part of every task's verification. |
| `npm run format:check` | Checks formatting with Prettier (non-mutating). | Part of every task's verification. |
| `npm test` | Runs the Vitest suite once (non-watch). | Part of every task's verification. |
| `npm run test:watch` | Runs Vitest in watch mode. | While developing/debugging tests. |

This file — not the root `README.md` — is the place to extend this guide, because `README.md` is a governance/context file the implementation worker is never permitted to modify (see `agent/tasks/ready/TASK-0001.md` → Forbidden changes).
