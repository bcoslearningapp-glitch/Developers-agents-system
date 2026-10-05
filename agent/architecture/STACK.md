# Technology Stack

Canonical decision record: `agent/architecture/decisions/ADR-0001-tech-stack.md` (accepted, human approval not required). This file is the operational summary; the ADR holds the rationale and rejected alternatives.

## Selected stack

| Concern | Choice | Notes |
|---|---|---|
| Language | TypeScript, `strict: true` | No `any` in domain/data layers; `unknown` + validation at the storage/import boundary. |
| UI runtime | React 19.x | Function components + hooks only. |
| Build/dev | Vite 7.x (`@vitejs/plugin-react`) | Static SPA output, `base: './'` so the build works from any subpath. |
| Routing | Internal hash router module (no dependency) | `#/today`, `#/progress`, `#/plan`, `#/weekly`, `#/history`; unknown hash → redirect to `#/today`. |
| Styling | Plain CSS + CSS Custom Properties (design tokens) + CSS Modules | No CSS framework. Tokens live in `src/styles/tokens.css`. |
| Charts | Inline SVG components owned by the project | No charting library. Every chart ships an equivalent text/table summary for accessibility. |
| Dates | Internal `src/domain/date.ts` on `YYYY-MM-DD` strings | No date library. |
| State | React `useReducer` + a single context provider | No external state manager, no data-fetching library. |
| Persistence | `localStorage`, one versioned JSON document | See `agent/architecture/DATA.md`. |
| Tests | Vitest + jsdom + `@testing-library/react` + `@testing-library/user-event` + `@testing-library/jest-dom` | Unit tests for domain, component/flow tests for critical flows. No E2E in v1. |
| Lint | ESLint 9 flat config + `typescript-eslint` + `eslint-plugin-react-hooks` + `eslint-plugin-jsx-a11y` | `jsx-a11y` is a required gate input, not optional. |
| Format | Prettier | Checked in CI-equivalent script, not only on save. |
| Runtime | Node.js `>=20.19` | Vite 7 engine requirement. Pin the local version in `.nvmrc`. |
| Package manager | npm with committed `package-lock.json` | Reproducible installs via `npm ci`. |
| Hosting target | Any static file host (reference: GitHub Pages) | No deployment performed until the M7 release gate. |

### Required npm scripts
These script names are contractual: tasks, quality gates, and review evidence reference them.

- `npm run dev` — local dev server.
- `npm run build` — type-check-clean production build to `dist/`.
- `npm run preview` — serve the built bundle locally.
- `npm run typecheck` — `tsc --noEmit`.
- `npm run lint` — ESLint over the project, zero warnings tolerated.
- `npm run format:check` — Prettier check (non-mutating).
- `npm test` — Vitest single run (non-watch), suitable for automation.
- `npm run test:watch` — Vitest watch mode for development.

## PRD rationale
- **No backend permitted (FR-015, `SCOPE.md`)** → static SPA, zero server code, zero external calls at runtime.
- **~30 day-records + 4 weekly reflections (`NON_FUNCTIONAL.md` performance)** → synchronous `localStorage`, no database, no pagination, no caching layer.
- **Business logic must be unit-testable without UI (`NON_FUNCTIONAL.md` maintainability)** → framework-free `src/domain/**` and Vitest.
- **Typed codebase + static checks are quality gates** → TypeScript strict, ESLint, Prettier, all wired as named npm scripts so evidence is reproducible.
- **WCAG 2.1 AA target, keyboard operability, contrast** → semantic HTML first, `eslint-plugin-jsx-a11y` in the lint gate, owned SVG charts with text equivalents, `@testing-library/user-event` for keyboard flow tests.
- **Responsive ~360px → desktop (FR-016)** → CSS with a small token-driven breakpoint set; no framework-imposed grid.
- **Calm/minimal, non-decorative visual system (`agent/design/IMPLEMENTATION_RULES.md`)** → owned CSS tokens and owned chart rendering rather than a library's default look.
- **Dependency-light instruction (PRD "Platform constraints")** → four runtime-relevant packages (`react`, `react-dom` + build/test tooling as devDependencies); everything else is dev tooling.

## Version policy
- Pin exact versions in `package.json` where practical; always commit `package-lock.json`; installs in automation use `npm ci`.
- Track the current major of React, Vite, and Vitest. Major upgrades are deliberate tasks with their own verification evidence, never incidental to a feature task.
- Patch/minor security updates may be taken inside any task that already touches dependencies, provided all gates still pass and the change is reported.
- **Adding any new runtime dependency requires an ADR** (supply-chain rule in `.claude/rules/30-security.md`). New *dev* dependencies must be justified in the implementation report.
- No dependency may be added that performs network I/O at runtime, injects third-party scripts, or loads remote fonts/assets.
- Node: support `>=20.19`; do not use APIs newer than that baseline in build/test config.

## Constraints
- `src/domain/**` must not import React, `localStorage`, `window`, `document`, or anything from `src/data/**`, `src/state/**`, `src/views/**`, or `src/ui/**`. Enforced by review, and by lint rules where practical.
- `src/data/**` may use `localStorage` and `src/domain/**` types only; it must not import React or view code.
- No derived value (adherence score, streak, phase, day status, insight) is ever persisted — all are computed from stored entries at read time (see `DATA.md`).
- No `dangerouslySetInnerHTML`, no `eval`, no dynamic script injection anywhere in the app.
- No analytics, telemetry, error-reporting SDK, remote font, or CDN asset in v1.
- Build output must be fully functional when served from a subdirectory and from `file://`-like static hosts (hence relative base + hash routing).
- Browser support: latest evergreen Chrome, Safari, Firefox, Edge (`NON_FUNCTIONAL.md`). No IE/legacy transpilation targets, no polyfill bundle.
