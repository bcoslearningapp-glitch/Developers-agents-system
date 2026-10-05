# Architecture

## Current reality (existing projects)
**Greenfield.** As of 2026-09-06 the repository contains only the agent control-plane (`agent/**`, `.claude/**`, `tools/agents/**`) and no application code, no `package.json`, no build, and no tests. There is no legacy system, no existing user data, and therefore no migration constraint. Everything below is target state to be built, starting at milestone M1.

## Target architecture

A single-page, local-first web application. One browser tab is the whole system: there is no server, no API, no database, and no network dependency at runtime. Loading the page bootstraps the app from `localStorage`; every user action mutates in-memory state and writes back synchronously; every displayed number is derived from stored entries on read.

```
┌──────────────────────── Browser (single device, single user) ────────────────┐
│                                                                              │
│   views/  Today · Progress · 30-Day Plan · Weekly Review · History           │
│      │  reads derived view models, dispatches intents                        │
│      ▼                                                                       │
│   state/  JournalProvider (reducer + context) ── selectors (memoized) ──┐    │
│      │  load on boot, apply intent, persist, expose status              │    │
│      ▼                                                                  ▼    │
│   data/   repository → migrations → validation → storage adapter    domain/  │
│      │                                                        (pure rules)   │
│      ▼                                                                       │
│   localStorage  (one versioned JSON document)        file download / upload  │
└──────────────────────────────────────────────────────────────────────────────┘
```

Three architectural rules carry most of the design:

1. **Derived data is never stored.** Adherence score, day status, streaks, phase, averages, trends, and insights are computed from `entries` at read time. This removes an entire class of "aggregate out of sync after an edit" bugs (BR-7) and makes recomputation a non-feature: editing any day automatically corrects everything downstream.
2. **The domain layer is pure.** `src/domain/**` contains no React, no browser APIs, no I/O. Every business rule (BR-1–BR-9) is a pure function over plain data, unit-testable in isolation, exactly as `NON_FUNCTIONAL.md` requires.
3. **One write path.** All persistence goes through a single repository that owns the versioned envelope, validation, and migration. No view or component touches `localStorage` directly.

### Layering and dependency direction

`views` → `state` → `data` → (browser storage)
`views` / `state` / `data` → `domain` (leaf; depends on nothing)
`views` → `ui` (presentational primitives; `ui` depends on `domain` types at most)

Imports never point upward or sideways across siblings (`views/today` must not import from `views/history`; shared pieces move to `ui/` or `domain/`).

## Boundaries/modules

### `src/domain/**` — business rules (pure, framework-free)
| Module | Responsibility | Rules |
|---|---|---|
| `model` | Entity types, indicator list (6 fixed ids, ordered), day-type list (5 fixed ids), phase definitions, journey length constant (30) | FR-002, FR-005, FR-006 |
| `date` | Calendar-date arithmetic on `YYYY-MM-DD` strings: today-as-local-date, add/diff days, compare, format for display. Timezone- and DST-safe by construction | BR-1 |
| `journey` | Derive Day 1–30 dates from a start date; map a date to a day number and back; classify a date as before/inside/after the journey | FR-001, BR-1, BR-9 |
| `phases` | Map day number → phase (1: days 1–7, 2: 8–14, 3: 15–21, 4: 22–30) and phase → its day range/title | FR-006, BR-2 |
| `scoring` | Adherence score for a day entry: `round((sum of 6 ratings / 30) × 100)`; returns "no score" (not 0) when the day is not fully rated | FR-003, BR-3 |
| `completion` | Whether a day entry is complete (all six indicators rated); day status resolution (`today`/`completed`/`missed`/`future`) | BR-4, BR-6 |
| `streaks` | Current streak and best streak over the journey's elapsed dates | BR-5 |
| `stats` | Overall adherence, completed-day count, per-indicator averages, 30-day score series, per-indicator series, per-week averages | FR-009, FR-011 |
| `insights` | Insight rules computed only from logged entries, gated behind the ≥3-completed-days sufficiency rule; returns an explicit "insufficient data" result below the threshold | FR-009, BR-8 |

The insight generator must return structured results (rule id + the numbers that triggered it), not prose strings assembled from nothing — the VISION principle "insight only from real data" is an architectural constraint, not copy guidance.

### `src/data/**` — persistence boundary
| Module | Responsibility |
|---|---|
| `storageAdapter` | Thin port over `localStorage` (`read`/`write`/`remove` a string by key) with an in-memory implementation for tests and a guarded path for unavailable/quota-exceeded storage. |
| `envelope` | Serialize/deserialize the versioned document wrapper (`schemaVersion` + payload). |
| `validate` | Parse `unknown` → typed document; reject/repair unknown shapes; never trust stored or imported JSON. |
| `migrations` | Ordered version-to-version upgrade steps; refuse (not guess) on a future `schemaVersion`. |
| `repository` | The only module allowed to read/write the store. Exposes load, save-document, and per-entity update operations; guarantees a durable write before reporting success. |
| `portability` | Build the export payload and parse/validate an import payload; import is applied only through the repository after explicit confirmation. |

### `src/state/**` — application state
A single `JournalProvider` (reducer + context) holding: load status (`loading` / `ready` / `error` / `storage-unavailable`), the journey document, and a save status. Intents: complete onboarding, upsert a day entry, upsert a weekly reflection, import document, reset. Memoized selectors expose derived view models built from `domain` functions, so recomputation after an edit is automatic and centralized. No component keeps a second copy of persisted truth.

### `src/app/**` — shell
Hash router (parse `location.hash` → route, subscribe to `hashchange`, unknown route → Today), the application shell (header, primary navigation across the five destinations, main landmark, skip link), and route-level error/empty boundaries.

### `src/views/**` — one folder per destination
`today`, `progress`, `plan`, `weekly`, `history`. Views compose `ui` primitives and read from `state` selectors. Views contain no business arithmetic and no storage access.

### `src/ui/**` — presentational primitives
Buttons, cards, rating input, section headers, empty/error/loading states, chart primitives (line/bar SVG + their text summaries). Stateless where possible; no domain rules inside.

### `src/styles/**`
`tokens.css` (color, spacing scale, typography, radii, breakpoints as custom properties) and `global.css` (reset, base typography, focus-visible styling). Component styles use CSS Modules colocated with components.

## Key flows

### 1. Boot
Mount → repository load → (a) nothing stored: state `ready` with an empty document and `onboardingCompleted = false` → onboarding; (b) stored and valid: migrate if needed, persist migrated form, state `ready`; (c) stored but corrupt/unparseable: preserve the raw string under a quarantine key, start empty, and surface a visible non-fatal error message (never a blank screen, never a silent wipe — `NON_FUNCTIONAL.md` observability); (d) storage unavailable (private mode/blocked): state `storage-unavailable`, app is readable but clearly warns that nothing can be saved.

### 2. Onboarding (FR-001)
User confirms or picks a start date (default today) → validated as a calendar date → `journey.startDate` written with `onboardingCompleted = true` → `journey` module derives Day 1–30 and phases → redirect to Today. Runs once per journey; re-running is not offered in v1 (BR-9).

### 3. Daily save (FR-002–FR-005, FR-007)
Today resolves the current date → day number and phase from `journey`/`phases` → loads that date's entry (or a blank one) → user edits ratings/day type/reflection in local component state → the live score is computed by `scoring` on every change without saving → on save, the entry is upserted through the repository, the write completes synchronously, and only then does the UI report "saved". Ratings save independently of reflection and day type (FR-004/FR-005 are optional and never block). If today is outside the journey range, the view explains the state instead of rendering inputs.

### 4. Aggregate recompute (BR-7)
There is no explicit recompute step. A successful save replaces the entry in state; selectors recompute score, status, streaks, averages, trends, and insights from the new document. Every dependent view (Progress, Plan, Weekly, History) is therefore correct by construction after any edit of any day, past or present. Insight output stays gated by the ≥3-completed-days rule (BR-8).

### 5. Export (FR-013)
`portability` builds `{ app marker, schemaVersion, exportedAt, document }` → serialized to a JSON Blob → downloaded via an object URL with a dated filename. Nothing leaves the device; no upload endpoint exists. The UI states plainly that the file is an unencrypted backup the user is responsible for storing.

### 6. Import (FR-014)
User picks a file → read locally → parse and validate shape, app marker, and `schemaVersion` → reject with a specific, non-technical error if invalid or newer than supported → show a confirmation step that names what will be replaced → on confirm, migrate to the current version, persist through the repository, and reload state. Import never merges silently in v1: it replaces, and only after explicit confirmation. Invalid files leave existing data untouched.

## Traceability
| Requirement | Home |
|---|---|
| FR-001, BR-1, BR-9 | `domain/journey`, onboarding flow |
| FR-002, FR-004, FR-005 | `views/today`, `ui` rating input, `data/repository` |
| FR-003, BR-3 | `domain/scoring` |
| FR-006, BR-2 | `domain/phases` |
| FR-007 | `views/today` |
| FR-008, FR-012, BR-7 | `views/history`, state selectors |
| FR-009, BR-5, BR-8 | `domain/streaks`, `domain/stats`, `domain/insights`, `views/progress` |
| FR-010, BR-6 | `domain/completion`, `views/plan` |
| FR-011 | `domain/stats`, `views/weekly` |
| FR-013, FR-014 | `data/portability` |
| FR-015 | `data/**`, absence of any network client |
| FR-016 | `src/styles/**`, `src/app` shell, all views |
