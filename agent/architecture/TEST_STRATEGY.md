# Test Strategy

Guiding principle from `AGENTS.md`: passing tests are necessary but not sufficient — the applicable gates in `agent/quality/QUALITY_GATES.md` are part of acceptance. The testing effort here is deliberately concentrated where the product's correctness actually lives: **the business rules (BR-1–BR-9) and the persistence/migration path**, because a wrong streak or a lost journal is unrecoverable for the user, whereas a visual imperfection is not.

Tooling: Vitest + jsdom + `@testing-library/react` + `@testing-library/user-event` + `@testing-library/jest-dom` (ADR-0001). No E2E framework in v1.

## Test pyramid/levels

### Level 1 — Domain unit tests (`src/domain/**`) — the heaviest layer
Pure functions, no DOM, no mocks, table-driven where the rule is arithmetic. Required coverage per rule:

| Rule | Required cases |
|---|---|
| BR-1 journey range | Day 1 = start date; Day 30 = start + 29; month boundary; year boundary; leap-day start; date before start / after day 30 classified correctly. |
| BR-2 phase mapping | Boundary days 1, 7, 8, 14, 15, 21, 22, 30 map to phases 1,1,2,2,3,3,4,4; day 0 and 31 are invalid, not silently clamped. |
| BR-3 score | All 5s → 100; all 0s → 0; mixed sums round as specified; a day with any unrated indicator has **no score** (not 0); a day with no entry has no score and is not a 0% day. |
| BR-4 completion | Six ratings present → complete; five present + one `null` → not complete; day type/reflection present but ratings missing → not complete; reflection empty but ratings complete → complete. |
| BR-5 streaks | No completed days; single day; consecutive run ending today; run ending yesterday with today unlogged; gap in the middle; best ≠ current; missed past day breaks the streak; future dates never count. |
| BR-6 day status | `today` wins over `completed`/`missed` for the current date; past+complete → `completed`; past+incomplete/absent → `missed`; future → `future`, including a future date that somehow holds an entry. |
| BR-8 insights | 0, 1, 2 completed days → explicit "insufficient data" result and **no** insight output; 3+ → insights returned; every returned insight traces to real logged numbers; no insight is produced from unlogged days. |
| Stats | Averages ignore unlogged days (not counted as 0); per-indicator averages; per-week averages including the 9-day week 4; trend series length and ordering; empty-data safety (no division by zero, no `NaN`). |
| Date module | Add/diff across DST transitions in both directions, across months/years, leap years; "today" resolves to the **local** calendar date, not a UTC-shifted one; invalid strings rejected. |

Determinism rule: never call the real clock in a test. The current date is injected/faked (fake timers or an injected "today" parameter), and time-dependent tests pin an explicit date and timezone.

### Level 2 — Data layer tests (`src/data/**`)
- Round-trip: document → write → read → identical document.
- **Reload simulation:** write through one repository instance, construct a fresh instance over the same storage, and assert the data is intact. This is the direct test of the "no data loss on refresh/close" NFR and the M1 exit criterion.
- Migration: for every historical `schemaVersion`, a stored fixture upgrades to the current shape with no content loss; migrated result is written back; fixtures for old versions are kept permanently.
- Defensive reads: unparseable JSON, missing `schemaVersion`, wrong-typed fields, unknown extra keys, out-of-range ratings, `schemaVersion` newer than supported → each produces the specified outcome (quarantine / refuse / reject) and **never** throws past the boundary or wipes data silently.
- Storage failures: adapter unavailable (throws on access) and quota-exceeded on write → surfaced as the defined error states, prior data untouched.
- Import validation: non-JSON, valid JSON without the app marker, structurally invalid payload, prototype-pollution keys (`__proto__`, `constructor`), oversized file → all rejected with existing data unchanged (`SECURITY.md` T2).
- Storage is exercised through the in-memory adapter for speed and through jsdom `localStorage` at least once to prove the real adapter works.

### Level 3 — Component / flow tests (`src/views/**`, `src/app/**`, `src/state/**`)
React Testing Library, queried by accessible role/label (never by CSS class or test-id where a role exists) — this makes the tests double as accessibility assertions. Interactions use `user-event`, including keyboard-only paths.

Scope: the critical flows below, plus per-view empty/loading/error states, and the shell's navigation and route resolution.

### Not automated in v1 (deliberate)
- Cross-browser/real-browser E2E, file-download and file-picker behaviour, and visual regression. jsdom cannot honestly verify these; they are covered by the manual release checks below instead of by tests that would pretend.
- Performance benchmarking: unnecessary at 30 records.
- Automated contrast/visual-design verification: manual, against `agent/design/IMPLEMENTATION_RULES.md`.

## Critical flows

Each must have at least one flow-level test asserting the user-visible outcome, not internal state:

1. **Onboarding (FR-001)** — first run shows onboarding; a start date is accepted (default today); the app lands on Today for Day 1; onboarding does not reappear after reload.
2. **Daily save (FR-002–FR-005, FR-007)** — rate six indicators, see the live score update before saving, save, and observe the saved state; reflection and day type are optional and do not block saving; reload keeps the entry and score.
3. **Edit a past day (FR-008, BR-7)** — open a past day from History/Plan, change a rating, save, and observe that the day's score **and** the dependent aggregates (streak/averages/status) reflect the change.
4. **Out-of-range Today (FR-007)** — when today is before the start date or after day 30, the view explains the state and does not offer entry controls.
5. **Progress gating (FR-009, BR-8)** — with fewer than 3 completed days, Progress explains that more data is needed and shows no insights; with 3+, insights appear and match the logged data.
6. **Export (FR-013)** — export produces a payload containing the full document with the app marker and schema version, and the UI states that the file is an unencrypted backup.
7. **Import with confirmation (FR-014)** — a valid file requires explicit confirmation before applying; cancelling changes nothing; an invalid file is rejected with a clear message and leaves data untouched; export → import → export round-trips losslessly.
8. **Corrupt store recovery** — a corrupted stored value yields a usable app with a visible explanatory message rather than a blank screen or a crash.
9. **Navigation (FR-016, M1)** — all five destinations are reachable from the shell, reachable directly by hash URL, keyboard-operable, and an unknown route resolves sensibly.

## Environments

- **Local development:** Node `>=20.19`, `npm ci`, `npm run dev`. Vitest in jsdom; no external services, no fixtures fetched from the network, no seeded backend — the app has none.
- **Automated verification (the command set every task reports):** `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm test`, `npm run build`. These names are contractual (`STACK.md`).
- **Manual verification environment:** the built bundle via `npm run preview`, exercised in at least one Chromium-based browser and, before release, in Safari (the `localStorage`/private-mode and file-download edge cases live there). Responsive checks at ~360px, ~768px, and a desktop width, using real viewport resizing rather than only devtools emulation for the release pass.
- **Test data:** synthetic only. Never commit real journal content (`SECURITY.md`). Shared factories build documents/entries for tests so fixtures stay consistent as the schema evolves.

## Release evidence

**Per task (in `agent/reports/implementation/TASK-XXXX.md`):**
- Exact commands run and their results for every applicable script above (a task that touches no code still states why).
- New/changed tests listed, with the requirement or business rule each one covers.
- For UI tasks: which viewport widths were checked, keyboard-path result, and the empty/loading/error states exercised.
- Any deviation from this strategy stated explicitly rather than omitted.

**Per milestone / release (`agent/quality/RELEASE_CHECKLIST.md` and M7):**
- Full gate run green: build, typecheck, lint, format, tests.
- All nine critical flows verified manually in a real browser on desktop and mobile widths, including the file download and file-picker steps that jsdom cannot cover.
- Accessibility pass: keyboard-only completion of onboarding and a daily entry; visible focus throughout; contrast verified against WCAG AA for the final palette; screen-reader labels on icon-only controls; each chart has a readable non-visual equivalent.
- Privacy pass: browser devtools network tab shows **zero** outbound requests carrying journal content during a full session (onboarding → daily save → export → import); no journal content in console output.
- Data-safety pass: refresh/close-and-reopen retains data; export → import round-trip is lossless; a corrupt store recovers with a quarantine copy.
- Any known limitation or residual risk recorded rather than quietly accepted.
