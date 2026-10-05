# ADR-0001 — Frontend stack for a local-only, no-backend 30-day journal

- Status: accepted
- Date: 2026-09-06
- Related requirements/tasks: `FR-015` (local persistence, no backend), `FR-016` (responsive), `agent/product/NON_FUNCTIONAL.md` (maintainability/testing, accessibility, browser support), `agent/product/PRD.md` "Platform constraints", milestone `M1`, `TASK-0001`.

## Context
Kaizen is a single-user, local-first web journal with no account, no backend, and no external API. The whole data set is one journey: at most 30 day-records, 4 weekly reflections, and a settings object — a few tens of kilobytes. Five views must be responsive, accessible (WCAG 2.1 AA target), and calm/minimal. Business rules (adherence score, phase mapping, streaks, day status, insight gating) must be unit-testable independently of UI, and the PRD requires a typed codebase with type-check and lint as quality gates.

The PRD explicitly leaves the stack to the Architect and forbids a backend for core functionality in v1. The dominant risks are the opposite of scale: overengineering (a state library, ORM-like data layer, chart framework, or E2E grid for a 30-record app) and dependency churn in a project that must stay maintainable by a small implementation loop.

## Decision
Adopt a small, dependency-light, statically-hosted SPA:

- **Language:** TypeScript in `strict` mode.
- **UI framework:** React (v19 line) — chosen for ubiquity, stable mental model, and testing-library support.
- **Build tool / dev server:** Vite (v7 line) with the React + TypeScript template. Build output is a static bundle with a relative base path (`base: './'`).
- **Routing:** in-app hash-based routing (`#/today`, `#/progress`, `#/plan`, `#/weekly`, `#/history`), implemented as a small internal module — **no router dependency**. Hash routing keeps deep links working on any static host without server rewrite rules.
- **Styling:** plain CSS with CSS Custom Properties as design tokens, plus CSS Modules (built into Vite) for component scoping. **No CSS framework.**
- **Charts:** hand-authored inline SVG chart components (thin line/bar), **no charting library**. Max 30 data points; the design rules demand calm, chrome-free visuals and a non-color-dependent text summary alongside each chart, which is easier to guarantee in owned SVG than in a generic chart library.
- **Dates:** no date library. A dedicated internal `domain/date` module operates on `YYYY-MM-DD` calendar-date strings and is unit-tested for month/year boundaries, leap years, and DST transitions.
- **State:** React built-ins (`useState`/`useReducer`/`useContext`) via a single journal state provider. **No Redux/Zustand/Jotai/TanStack Query.**
- **Persistence:** `localStorage`, one versioned JSON document (see `agent/architecture/DATA.md`). **Not IndexedDB.**
- **Testing:** Vitest + jsdom + `@testing-library/react` + `@testing-library/user-event` + `@testing-library/jest-dom`. Unit tests for domain rules; component/flow tests for critical flows. **No E2E/browser-grid tooling in v1.**
- **Lint/format:** ESLint 9 flat config with `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-jsx-a11y`; Prettier for formatting.
- **Runtime/package manager:** Node.js `>=20.19` (Vite 7 requirement), npm with a committed lockfile.
- **Hosting target:** any static file host (GitHub Pages as the reference target). No hosting account, DNS, or deployment is activated by this ADR.

Non-negotiable structural rule that follows from this stack: `src/domain/**` is pure TypeScript with no React and no browser API imports, so business rules stay testable in isolation.

## Alternatives considered
- **No framework (vanilla TS + DOM).** Smallest dependency surface, but five stateful views with live recompute, editable history, and flow tests would mean hand-rolling rendering and event wiring — more owned code and weaker test ergonomics than React. Rejected.
- **Svelte / SvelteKit or Solid.** Smaller runtime output and arguably nicer ergonomics, but SvelteKit implies routing/SSR machinery this product does not need, and the ecosystem familiarity of the implementation loop is lower. Rejected as an unnecessary risk, not on technical merit.
- **Next.js / Nuxt / Remix.** Server-oriented frameworks for a product that is forbidden a backend. Rejected as overengineering.
- **`react-router`.** Proven, but adds a dependency with a history of breaking API generations for five flat destinations; the app needs no nested layouts, loaders, or data routers. Rejected in favour of ~1 small internal module. Revisit if route count or nesting grows materially.
- **IndexedDB (raw or via `idb`/Dexie).** Correct for large or streaming data; here it adds asynchronous complexity and a dependency for <100 KB of JSON. Rejected. Revisit only if a future feature stores blobs or many journeys.
- **Charting library (Recharts, Chart.js, visx).** Large dependency, opinionated visual chrome to strip back, and accessibility that still needs manual work. Rejected for two simple 30-point charts.
- **Tailwind CSS.** Popular, but adds build config and utility-class churn for a deliberately restrained, token-driven visual system. Rejected; CSS custom properties express the design tokens more directly.
- **date-fns / Day.js / Temporal polyfill.** Reasonable fallback, but the app needs only "add N days", "diff in days", "today as a local calendar date", and formatting. Rejected for v1; if the internal date module proves error-prone in review, adopting `date-fns` is the sanctioned escape hatch and requires only a superseding ADR.
- **Playwright/Cypress E2E.** Deferred. Component/flow tests in jsdom cover onboarding, daily save, and export/import for a local-only app; browser automation can be added at M7 if evidence demands it.

## Consequences
**Positive**
- Very small dependency surface: one UI runtime, one build tool, one test runner, plus lint/format dev tooling. Low supply-chain and upgrade burden.
- Pure `src/domain/**` makes every business rule (BR-1–BR-9) directly unit-testable, satisfying the NFR that logic be tested independently of UI.
- `localStorage` + a single versioned document gives synchronous reads/writes, so "saved" can be reported only after a durable write with no async race — directly serving the no-data-loss NFR.
- Static output with a relative base path and hash routes deploys to any static host with zero server configuration.

**Negative / limits**
- `localStorage` is synchronous, ~5 MB per origin, and string-only. Acceptable for this data size; documented as a hard boundary in `DATA.md`. Growth beyond one journey with rich content would require an IndexedDB migration (new ADR).
- Hand-rolled routing and charts mean the project owns that code and its tests. Mitigated by keeping both intentionally minimal and required-tested.
- No E2E coverage in v1: real-browser regressions (e.g., Safari `localStorage` in private mode, file download behaviour) must be caught by manual verification in the release checklist.
- Clearing browser data or using a private window destroys the journal. This is inherent to the product's no-backend decision (PRD/VISION), and is mitigated only by export/import (FR-013/FR-014) plus explicit in-product copy.

**Operational / cost / security**
- Cost: none. All tooling is free and OSS (MIT/BSD-family licenses); no paid vendor, no cloud resource, no API spend, no subscription.
- Lock-in: none beyond ordinary frontend tooling. The domain layer is framework-free, so a UI change would not touch business rules.
- Security: no network calls, no credentials, no secrets in the repository, no third-party runtime scripts or fonts fetched from a CDN (self-host any webfont) — see `agent/architecture/SECURITY.md`.
- Migration: none — greenfield repository with no existing code or users.

## Human approval
**Not required.** This is an ordinary first-cycle engineering decision and does not cross any gate in `AGENTS.md`: it does not change product vision/scope/behaviour (the PRD explicitly delegates the stack choice); it introduces no paid service, subscription, cloud resource, API spend, or licensing cost; it introduces no vendor lock-in beyond standard OSS frontend tooling; it changes no authentication/authorization, privacy, or security policy (the local-only, no-account posture is set by the PRD, not by this ADR); it involves no data migration or destructive operation (greenfield); and it activates no deployment, domain, or production credential. Selecting a *static hosting target* here is a build-output decision only — actually publishing a production deployment remains a human decision gate and is out of scope until M7.
