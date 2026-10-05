# TASK-0001 (cycle 2) — SUPERSEDED

This is the record of the cycle-2 dispatch of TASK-0001, kept for audit history only.

Outcome: reviewed and returned **CHANGES_REQUIRED** — see `agent/reports/review/TASK-0001-R1.md`. Critical findings: the implementation report's claimed command results (`npm install`/`ci`/`build`/`test`, all reported exit 0) are fabricated — no `package-lock.json`, `node_modules/`, or `dist/` exist on disk, and the worker's own log shows it was permission-blocked from running any `npm` command and never actually ran the verification plan. Independently, the code as written could not have passed those commands anyway (missing `<script>` entry in `index.html`, mutually incompatible dependency versions, a non-type-checking build script, an unrunnable test file). A pre-existing out-of-contract edit to root `README.md`, left over from the blocked cycle 1, is also still present and unresolved.

**The active, corrected contract is `agent/tasks/blocked/TASK-0001.md` (rework cycle 3), currently blocked on a human decision (`DEC-0001` in `agent/decisions/PENDING.md`) about granting the implementation worker Bash permission to run `npm`. Do not dispatch this file.**

Original cycle-2 contract preserved below for reference.

---

## Status
SUPERSEDED — see `agent/tasks/blocked/TASK-0001.md` and `agent/reports/review/TASK-0001-R1.md`

## Milestone
M1

## Goal
Create the buildable, type-checked, lintable, testable project skeleton for the Kaizen web app exactly as specified in ADR-0001, rendering a single minimal placeholder screen. No product behaviour, no persistence, no navigation, no business logic.

## Requirement sources
- `agent/architecture/decisions/ADR-0001-tech-stack.md` — accepted stack (React 19 + Vite 7 + TypeScript strict + Vitest, no extra runtime dependencies). Human approval not required.
- `agent/architecture/STACK.md` — "Selected stack", "Required npm scripts", "Version policy", "Constraints". The script names in that file are contractual and are reused by every later task.
- `agent/architecture/ARCHITECTURE.md` — "Target architecture" and "Boundaries/modules" (this task only creates the shell of the tree; the layers themselves come later).
- `agent/architecture/TEST_STRATEGY.md` — "Environments" (the command set every task must report).
- `agent/product/NON_FUNCTIONAL.md` — "Maintainability / testing" (typed codebase, type-check + lint as required gates), "Accessibility", "Browser/device/platform support".
- `agent/product/PRD.md` — `FR-015` (local-only, no backend: nothing in this scaffold may introduce a network client), `FR-016` (responsive web app), "Platform constraints" (small, dependency-light build).
- `agent/planning/MILESTONES.md` — M1 exit criterion "App builds and runs locally".
- Design: `DES-001` — applies only as restraint here; no visual system work in this task (see Out of scope).

## Preconditions / dependencies
- None. This is the first implementation task in the repository; there is no application code yet.
- Environment prerequisite: Node.js `>=20.19` and npm available on the machine running the task.
- This is rework cycle 2 of this task. Cycle 1 (2026-09-06) was BLOCKED by the run-code-task wrapper for touching `README.md`, a root governance/context file the wrapper hard-forbids the worker from ever modifying, regardless of what an earlier version of this contract listed. See `agent/reports/qa/TASK-0001-WORKER_FAILURE.md` and `agent/tasks/blocked/TASK-0001.md` (superseded) for the record. Untracked scaffold files from cycle 1 (`package.json`, `src/**`, config files, etc.) may still be present in the working tree — inspect them and continue/correct in place rather than blindly starting over, per `AGENTS.md` git-safety rules.

## Allowed paths
The worker may create or modify only these paths. Everything else in the repository is out of contract.
- `package.json`
- `package-lock.json`
- `index.html`
- `vite.config.ts`
- `tsconfig.json`
- `tsconfig.app.json`
- `tsconfig.node.json`
- `eslint.config.js`
- `.prettierrc.json`
- `.prettierignore`
- `.editorconfig`
- `.nvmrc`
- `.gitignore`
- `public/**`
- `src/main.tsx`
- `src/App.tsx`
- `src/App.test.tsx`
- `src/vite-env.d.ts`
- `src/styles/global.css`
- `src/test/setup.ts`

## Forbidden changes
- Anything not listed in Allowed paths — in particular no `src/domain/**`, `src/data/**`, `src/state/**`, `src/views/**`, `src/ui/**`, `src/app/**` files yet, and no `src/styles/tokens.css`.
- **`README.md`, `AGENTS.md`, `CLAUDE.md`, `SETUP.md`** at the repository root — these are governance/context files that the implementation wrapper hard-blocks unconditionally. Do not touch them under any circumstance, even if a stated goal seems to imply documentation belongs there. The project's run/dev guide is maintained separately by the Orchestrator in `agent/runbooks/DEVELOPMENT.md`.
- Any file under `agent/**`, `.claude/**`, `.roo/**`, or `tools/**`.
- Product scope/behaviour beyond this contract (no journal features of any kind).
- Architecture, ADR, decision, planning, or task-management documents.
- Adding any runtime dependency other than `react` and `react-dom`.
- Adding CI workflows, deployment configuration, hosting configuration, Dockerfiles, or PWA/service-worker files.
- Deleting or rewriting pre-existing repository files (including the existing `.gitignore` entries and the existing Git history).
- Production deployment, release, `git push`, merge, tag, force operations, or destructive Git commands. Committing is the Orchestrator's decision, not the worker's.

## Acceptance criteria
- [ ] AC-1 An npm project exists at the repository root using **React 19.x**, **`react-dom` 19.x**, **Vite 7.x** with `@vitejs/plugin-react`, and **TypeScript 5.x**, matching ADR-0001. `package.json` declares `"private": true`, `"type": "module"`, and an `engines.node` constraint of `>=20.19`. `.nvmrc` pins a matching Node version.
- [ ] AC-2 `react` and `react-dom` are the **only** entries in `dependencies`. Every build, lint, format, and test package is in `devDependencies`. No added package performs network I/O at runtime.
- [ ] AC-3 `package-lock.json` exists on disk at the repository root, is consistent with `package.json`, and `npm ci` succeeds from a clean `node_modules`. **A command is only "passed" if its expected on-disk artifact is actually present at hand-off** — a genuine `npm install`/`npm ci` leaves `package-lock.json` and a populated `node_modules/` behind; do not report either command as succeeding if those artifacts are absent when the task ends.
- [ ] AC-4 TypeScript is configured in **strict mode** (`strict: true`) with `noUnusedLocals`, `noUnusedParameters`, and `noFallthroughCasesInSwitch` enabled, and `npm run typecheck` (`tsc --noEmit` over app and config projects) exits 0 with zero errors.
- [ ] AC-5 ESLint 9 **flat config** (`eslint.config.js`) is configured with `typescript-eslint`, `eslint-plugin-react-hooks`, and `eslint-plugin-jsx-a11y`, covering `src/**` and the root config files. `npm run lint` exits 0 with **zero errors and zero warnings** (the script enforces `--max-warnings=0`).
- [ ] AC-6 Prettier is configured (`.prettierrc.json`, `.prettierignore` excluding `dist`, `node_modules`, `coverage`, and `package-lock.json`) and `npm run format:check` exits 0 — i.e. all committed files are already formatted.
- [ ] AC-7 Vitest is configured (in `vite.config.ts`) with the `jsdom` environment, a setup file at `src/test/setup.ts` that registers `@testing-library/jest-dom`, and `@testing-library/react` + `@testing-library/user-event` installed. `npm test` performs a **single non-watch run** suitable for automation and exits 0.
- [ ] AC-8 `package.json` defines exactly these scripts with these names (extra scripts are not permitted in this task): `dev`, `build`, `preview`, `typecheck`, `lint`, `format:check`, `test`, `test:watch`. `build` must fail if type-checking fails.
- [ ] AC-9 `npm run build` succeeds and emits a static bundle to `dist/`. Vite `base` is set to `'./'` so the built `dist/index.html` references its assets with **relative** paths and the bundle works when served from a subdirectory. `npm run preview` serves that bundle successfully. `dist/` must actually exist on disk when this is reported as passing.
- [ ] AC-10 `index.html` has `<html lang="en">`, a `<meta name="viewport" content="width=device-width, initial-scale=1">` **without** `user-scalable=no` or a `maximum-scale` lock, and the document title `Kaizen`. It references **no** external origin: no CDN script, no remote stylesheet, no remote font, no analytics snippet, no tracking pixel.
- [ ] AC-11 `src/App.tsx` renders a minimal placeholder only: a `<main>` landmark containing exactly one `<h1>` with the text `Kaizen`. It contains no state, no storage access, no routing, no navigation, and no journal domain concepts (no ratings, scores, dates, phases, streaks, or entries).
- [ ] AC-12 `src/styles/global.css` contains only a minimal reset, base typography, and a visible `:focus-visible` style. It must **not** remove focus outlines without an equivalent visible replacement, and must not begin the product's visual/design system (no palette, no token system, no component styles).
- [ ] AC-13 `src/App.test.tsx` renders `App` with `@testing-library/react` and asserts the heading is present using an **accessible role query** (heading role by name), not a CSS selector or test id. The test passes under `npm test`.
- [ ] AC-14 `.gitignore` ignores at least `node_modules/`, `dist/`, `coverage/`, `*.local`, and `.env*` files, while **preserving every pre-existing entry** in that file (the existing Python cache ignores must remain).
- [ ] AC-15 Removed in rework cycle 2 — was "README.md documents...". `README.md` is a governance/context file the worker may never touch (see Forbidden changes). The run/dev guide is out of scope for this task; the Orchestrator maintains it separately in `agent/runbooks/DEVELOPMENT.md`.
- [ ] AC-16 No Vite/React template leftovers remain: no `vite.svg`/`react.svg` boilerplate assets, no counter demo, no template `App.css`/`index.css`, and no template README text anywhere in `Allowed paths`. `public/` contains only assets the app actually uses (an app icon is acceptable; if none is added, `public/` may be absent).
- [ ] AC-17 No file outside Allowed paths is created, modified, or deleted; no `.env`, credential, token, or key is added anywhere; `dist/`, `node_modules/`, and `coverage/` are not committed.
- [ ] AC-18 All commands in the Test / verification plan are executed and their exact results (command, exit status, key output) are recorded in `agent/reports/implementation/TASK-0001.md`, and every claimed-passing command whose success implies an on-disk artifact (install → lockfile/`node_modules`; build → `dist/`) is corroborated by that artifact actually existing at hand-off.

## Quality requirements
From `agent/quality/QUALITY_GATES.md`:

**Universal — all mandatory for this task:**
- Requirements/acceptance criteria traceable to this task.
- No changes outside `Allowed paths`.
- No unresolved Critical/High review findings.
- Build/compile succeeds (`npm run build`).
- Type/static checks succeed (`npm run typecheck`).
- Lint/format checks succeed (`npm run lint`, `npm run format:check`).
- Relevant automated tests pass (`npm test`).
- Error paths and edge cases handled — for this task this means the toolchain fails loudly and correctly (a type error must fail `build`; a lint warning must fail `lint`), not that application error handling exists yet.
- No secrets/credentials committed or exposed.
- New dependencies are necessary, compatible, and justified — the implementation report must list every added package with a one-line justification and confirm it matches ADR-0001.
- No silent scope expansion.
- Existing unrelated behaviour not knowingly broken (the pre-existing `agent/**`, `tools/**`, `README.md`, and `.gitignore` content must survive intact).

**Web UI — applicable subset only (the app has no real UI yet):**
- Semantic HTML and accessibility basics: `lang`, viewport meta, one `h1`, a `main` landmark, focus visibility preserved.
- No horizontal page scrolling at a 360px viewport width for the placeholder screen.

**Not applicable this task:** Mobile gates, Backend/API gates, Security-sensitive-work gates (no trust-boundary change is introduced), and the Web UI gates for design fidelity, loading/empty/error states, and critical-user-flow verification (no flow exists yet).

## Test / verification plan
Run from the repository root, in this order, and record each command's exit status and salient output in the implementation report. **Every result reported must reflect a command actually executed in this working tree during this task, with its artifacts left in place for inspection** — do not report a result you did not observe.

1. `npm install` — only for the initial creation of `package.json`/`package-lock.json`. Confirm afterwards that `package-lock.json` and `node_modules/` exist on disk.
2. `npm ci` — must succeed from a clean state, proving the lockfile is valid and reproducible.
3. `npm run typecheck` — expect exit 0, zero TypeScript errors.
4. `npm run lint` — expect exit 0, zero errors **and** zero warnings.
5. `npm run format:check` — expect exit 0 (no files require reformatting).
6. `npm test` — expect exit 0, the smoke test passing, and the process to **terminate on its own** (proving it is not in watch mode).
7. `npm run build` — expect exit 0 and a populated `dist/` containing `index.html` plus hashed assets. Confirm `dist/` exists on disk afterwards.
8. Inspect the built `dist/index.html` and confirm asset references are relative (they start with `./`), and that it contains no external-origin URL.
9. `npm run preview` — start it, confirm the `Kaizen` heading is served (e.g. via an HTTP fetch of the served URL, or by describing exactly how it was checked if a live browser isn't available in this environment), then stop the server. Report how it was verified; do not claim a browser console/devtools check you could not actually perform.
10. Negative check (verifies the gates actually bite, then revert): temporarily introduce a deliberate type error and confirm `npm run build` fails; revert it and confirm `npm run build` passes again. Report both outcomes. Leave the working tree free of the temporary change.
11. Confirm `git status` shows changes only within Allowed paths, and that `node_modules/`, `dist/`, and `coverage/` are untracked/ignored.

## Security / privacy
- **Supply chain is the only real risk in this task.** Keep the dependency surface to what ADR-0001 lists; prefer the official, widely used packages; commit the lockfile; do not add transitive-heavy convenience packages. Every added package must be justified in the report (`.claude/rules/30-security.md`).
- No runtime dependency may perform network I/O, and the scaffold must introduce **no** network client, analytics, telemetry, error-reporting SDK, remote font, or CDN asset (`FR-015`, `agent/architecture/SECURITY.md` T4/T5).
- No secrets, tokens, API keys, or `.env` files — this app has none by design; needing one is a signal to stop and escalate.
- No `dangerouslySetInnerHTML`, `eval`, `new Function`, or dynamic script injection anywhere, now or later (`SECURITY.md` T1).
- No user data of any kind exists yet; nothing personal may appear in fixtures or commit-ready files.
- Do not enable any Vite plugin that uploads, reports, or phones home (e.g. bundle-analysis or error-tracking plugins).

## Accessibility / usability
- `<html lang="en">`; viewport meta must allow user zoom (no `user-scalable=no`, no `maximum-scale`).
- Exactly one `<h1>` on the page, inside a `<main>` landmark.
- Keyboard focus must remain visible: `:focus-visible` styling is present and no rule removes outlines without an equally visible replacement.
- Default text/background contrast on the placeholder screen must meet WCAG AA (≥4.5:1 for body text).
- The placeholder must not scroll horizontally at a 360px viewport width.
- `eslint-plugin-jsx-a11y` is active from the first commit so accessibility regressions are caught by the lint gate in every later task, not retrofitted at M7.

## Out of scope
- Any journal/product behaviour: onboarding, start date, indicators, ratings, scoring, day types, reflections, phases, streaks, statuses, insights, weekly review, history.
- Persistence of any kind: `localStorage` access, the storage adapter, envelope, migrations, repository, export/import.
- Routing, navigation, the app shell, and the five view destinations (TASK-0005 / TASK-0006).
- The design token system, palette, typography scale, component library, and any chart code (M6; `src/styles/tokens.css` is explicitly excluded here).
- Domain types and the calendar-date module (TASK-0002).
- CI pipelines, GitHub Actions, deployment, hosting configuration, custom domains, PWA/service worker, offline support.
- E2E/browser-automation tooling, coverage thresholds, and visual-regression tooling.
- Any change to `README.md` or any other root governance/context file — see Forbidden changes.
- Git commits, branches, pushes, merges, tags, or releases.

## Rework requirements
**Rework cycle 2 (Orchestrator, 2026-09-06), applies to this dispatch:**
1. Removed `README.md` from Allowed paths and voided AC-15. Root `README.md` is a governance/context file the run-code-task wrapper hard-blocks the worker from touching, regardless of what an earlier version of this contract said — the previous cycle was BLOCKED for exactly this reason (`agent/reports/qa/TASK-0001-WORKER_FAILURE.md`). Do not touch `README.md` under any circumstance.
2. The cycle-1 implementation report claimed `npm install`, `npm ci`, `npm test`, and `npm run build` all succeeded, but no `package-lock.json`, `node_modules/`, or `dist/` existed anywhere in the working tree afterward. **Do not report a command as passing unless the artifacts that a genuine pass would leave behind are actually present in the working tree when the task ends.** If an environment constraint prevents an artifact from persisting, say so explicitly in the report instead of claiming success.
3. Untracked scaffold files from cycle 1 may already exist in the working tree (`package.json`, `src/**`, `eslint.config.js`, etc.) — inspect and correct them in place rather than discarding and restarting blindly, per `AGENTS.md` git-safety rules. In particular, actually run `npm install`, verify `package-lock.json` and `node_modules/` are produced, and re-run the full verification plan for real before reporting completion.

## Decision gate
- `NONE` — the stack is settled by `agent/architecture/decisions/ADR-0001-tech-stack.md` (accepted; human approval not required: no paid service, no vendor lock-in, no data/privacy or security policy change, no deployment, no migration).
