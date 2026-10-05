# Product Requirements Document

## Product summary
Kaizen is a local-first, no-account web journal that guides one user through a fixed 30-day discipline reset. The user picks a start date once; each of the 30 days is pre-mapped into one of four weekly phases. Every day the user rates six fixed indicators (0–5), optionally classifies the day type, and optionally writes a short structured reflection. The app computes a daily adherence score, tracks streaks and completion, and surfaces trends and insights derived only from the user's own logged data. All data is stored locally in the browser; the user can export/import it as a file.

## Users and jobs-to-be-done
- **The journaler.** "When I decide to reset my discipline, I want a fixed 30-day structure with daily check-ins, so I stay honest and can see my real patterns instead of relying on willpower alone."
- Single-user, single active journey. No multi-user, no coach/admin role, no account.

## Functional requirements
Use stable IDs such as `FR-001`.

- **FR-001 — Onboarding / start date.** On first use, the user selects a program start date (defaults to today). The app derives Day 1–30 dates and the phase (week) each date belongs to. Onboarding runs once per active journey.
- **FR-002 — Daily indicator rating.** For any day in the 30-day range, the user rates six fixed indicators from 0 to 5: Sleep quality and discipline; Spiritual routine; Digital entertainment control; Eating without overeating; Movement and exercise; Most important task completed.
- **FR-003 — Daily adherence score.** The app computes a 0–100% adherence score for each day from its six indicator ratings (see Business rules) as soon as ratings exist, and recomputes it on edit.
- **FR-004 — Daily reflection.** For any day, the user may write short free-text answers to: "What went well?", "Where did I lose control?", "What will I correct tomorrow?", "One thing I learned." Reflection is optional and does not block saving indicator ratings.
- **FR-005 — Day type classification.** For any day, the user may assign one day type from a fixed set: Normal work day, Long project day, Intensive sprint day, Friday / recovery day, Saturday / personal development day. Optional; defaults to unset.
- **FR-006 — Phase mapping.** The 30 days are grouped into four fixed phases: Week 1 "Reset the Environment" (Days 1–7), Week 2 "Build the Foundations" (Days 8–14), Week 3 "Build Capacity" (Days 15–21), Week 4 "Consolidate the System" (Days 22–30). Every day belongs to exactly one phase.
- **FR-007 — Today.** A dedicated view shows the current day's date, day number ("Day X of 30"), phase, the six indicator inputs, day type selector, reflection fields, and the live computed adherence score, with save. If today falls outside the active 30-day range (before start or after day 30), the view explains this state instead of showing entry controls.
- **FR-008 — Edit past days.** The user can open and edit the entry for any past day within the 30-day range from History or the 30-Day Plan. Edits immediately recompute dependent aggregates.
- **FR-009 — Progress.** A dedicated view shows: overall adherence (average score across completed days), current streak, best streak, count of completed days, average score per indicator, a 30-day score trend, per-indicator trends over the 30 days, and insights generated only from the user's own logged data (see Business rules for the data-sufficiency rule).
- **FR-010 — 30-Day Plan.** A dedicated view shows all 30 days grouped by their four phases, each day tagged with a status (completed / missed / today / future), and lets the user open any day's detail.
- **FR-011 — Weekly Review.** A dedicated view lets the user open any of the four weeks (phases) and see that week's average adherence and per-indicator averages, plus a single weekly reflection field (distinct from daily reflections) the user can write/edit once per week.
- **FR-012 — History.** A dedicated view lists all days with a saved entry (or all days up to today), lets the user open any past day, and edit it in place (same fields as FR-002/FR-004/FR-005).
- **FR-013 — Export.** The user can export all of their data (start date, all day entries, weekly reflections, settings) as one downloadable JSON file at any time.
- **FR-014 — Import.** The user can import a previously exported JSON file. Because import can overwrite existing local data, the app requires an explicit confirmation step before applying it, and validates the file's shape before accepting it.
- **FR-015 — Local persistence, no backend.** All application data persists locally in the browser (survives reload/close). No account, sign-in, or backend exists in v1; no journal content is transmitted over the network.
- **FR-016 — Responsive experience.** All five views (Today, Progress, 30-Day Plan, Weekly Review, History) are fully usable and visually correct on both desktop and mobile viewport widths.

## User journeys
1. **First run / onboarding.** User opens the app → sees a calm intro explaining the 30-day structure → picks a start date (or accepts today) → lands on Today for Day 1.
2. **Daily check-in.** User opens the app on a given day → lands on Today → rates six indicators → optionally sets day type and writes reflection → sees the computed score → saves.
3. **Reviewing a week.** At the end of a phase, user opens Weekly Review → selects the completed week → sees the week's averages → writes a weekly reflection.
4. **Checking progress.** User opens Progress at any point → sees overall adherence, streaks, per-indicator averages, and trend charts → reads insights drawn from their own data.
5. **Revisiting history.** User opens History or 30-Day Plan → selects a past day → reviews or edits that day's ratings/reflection/day type.
6. **Backing up / moving devices.** User opens settings → exports data to a file → later, on the same or another device/browser, imports that file after confirming the overwrite.

## Business rules
- **BR-1 — Fixed length.** A journey is exactly 30 days starting on the user-chosen start date; Day 1 = start date, Day 30 = start date + 29 days.
- **BR-2 — Phase boundaries.** Week 1 = Days 1–7, Week 2 = Days 8–14, Week 3 = Days 15–21, Week 4 = Days 22–30 (9 days, to absorb the remainder of 30 ÷ 4 into the final consolidation phase).
- **BR-3 — Adherence score formula.** `score = round((sum of the 6 indicator ratings / 30) × 100)`. A day with no ratings saved has no score (not zero) and is treated as unlogged, not as a 0% day.
- **BR-4 — Day completion.** A day counts as "completed" for streak/completion/average metrics once all six indicators are rated and saved for that day. Day type and reflection are optional and do not affect completion.
- **BR-5 — Streaks.** Current streak = the number of consecutive completed days ending at the most recent completed day, counting backward with no gap among past dates that have already occurred. Best streak = the longest such consecutive run found anywhere in the journey so far. A past date within the range with no saved entry breaks the streak.
- **BR-6 — Day status (30-Day Plan/History).** For each date in the range: `today` if it is the current date; `completed` if all six indicators are saved; `missed` if the date is in the past and not completed; `future` if the date has not yet occurred.
- **BR-7 — Editable history.** Any past or current day within the 30-day range can be edited at any time; saving an edit recomputes that day's score and all aggregates that depend on it (streaks, averages, trends, insights).
- **BR-8 — Insight sufficiency.** Progress insights are computed exclusively from the user's saved entries and are only shown once at least 3 completed days exist; below that threshold the Progress view explains that more data is needed instead of guessing.
- **BR-9 — Single active journey.** Only one journey (one start date, one set of 30 days) is active at a time in v1; starting a new journey after completion is out of scope for v1 (see Out of scope).

## Platform constraints
- Responsive web application, usable in modern evergreen desktop and mobile browsers (see `NON_FUNCTIONAL.md` for the supported list).
- No specific frontend framework or hosting platform is mandated by the product; the Architect selects the stack against `STACK.md`, optimizing for a small, dependency-light, local-first build.
- No backend service, database server, or third-party API is required or permitted for core functionality in v1.

## Data and privacy constraints
- All journal content (ratings, day types, reflections, dates) is personal in nature; it is stored only in the user's browser (e.g., `localStorage`/IndexedDB) and is never sent to a server or third party in v1.
- Export files are plain, unencrypted JSON under the user's own control; the app must make clear (in-product copy) that the exported file is an unencrypted local backup the user is responsible for storing safely.
- Import is destructive to existing local data unless the Architect designs an explicit merge strategy; at minimum, import must require explicit user confirmation before overwriting.
- No analytics/telemetry that transmits journal content off-device is included in v1.

## Non-functional requirements
Link to `NON_FUNCTIONAL.md`.

## Design references
Link to `agent/design/SOURCES.md`. No Figma/visual source exists yet; `DES-001` is the user-provided written direction, recorded there and expanded into constraints in `agent/design/IMPLEMENTATION_RULES.md`.

## Out of scope
See `agent/product/SCOPE.md` for the authoritative list (accounts/auth, backend/sync, notifications, sharing, custom indicators/day types, multiple concurrent journeys, localization, native mobile apps, in v1).

## Acceptance at product level
The v1 product is acceptable when a user can, without an account or network dependency: complete onboarding once; log all 30 days' indicators/day type/reflection with correct live scoring; see correct phase grouping, streaks, completion counts, per-indicator averages, and trend/insight data driven only by their own entries; complete a weekly review for each of the four weeks; browse and edit any past day from History; and export and re-import their full data set losslessly — all with a calm, minimal, responsive UI on both desktop and mobile.
