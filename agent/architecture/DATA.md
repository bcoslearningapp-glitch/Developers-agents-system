# Data Architecture

All data is local to one browser profile on one device. There is no server, no database, and no synchronization. The entire data set is a single JSON document.

## Entities/models

### Shared value types
- **CalendarDate** — a local calendar date as `YYYY-MM-DD`. This is the canonical day key everywhere. Never store `Date` objects, timestamps, or UTC-shifted ISO date-times as a *day identity*: a UTC instant is not a calendar day and produces off-by-one-day bugs across timezones and DST.
- **Timestamp** — ISO 8601 date-time string, used only for audit fields (`createdAt`, `updatedAt`, `exportedAt`), never for day identity.
- **Rating** — integer `0..5`, or `null` when the indicator has not been rated.

### Fixed vocabularies (not user-editable in v1 — `SCOPE.md`)
Indicators (six, fixed order — this order is the display order and the array order in any series):

| id | Label (FR-002) |
|---|---|
| `sleep` | Sleep quality and discipline |
| `spiritual` | Spiritual routine |
| `digital` | Digital entertainment control |
| `eating` | Eating without overeating |
| `movement` | Movement and exercise |
| `mit` | Most important task completed |

Day types (five, optional — FR-005): `normal` (Normal work day), `long_project` (Long project day), `sprint` (Intensive sprint day), `friday_recovery` (Friday / recovery day), `saturday_growth` (Saturday / personal development day). Unset is represented by `null`.

Phases (four, fixed — FR-006/BR-2): `1` "Reset the Environment" (days 1–7), `2` "Build the Foundations" (8–14), `3` "Build Capacity" (15–21), `4` "Consolidate the System" (22–30).

### JournalDocument (the persisted payload)
| Field | Type | Notes |
|---|---|---|
| `journey` | `Journey \| null` | `null` until onboarding completes. One journey only (BR-9). |
| `entries` | map keyed by `CalendarDate` → `DayEntry` | Sparse: only days the user has touched exist. A missing key means *unlogged*, which is distinct from a 0% day (BR-3). |
| `weeklyReflections` | map keyed by phase number `"1".."4"` → `WeeklyReflection` | Sparse; at most four. |
| `settings` | `Settings` | Local UI/product preferences only. |

**Journey**
| Field | Type | Notes |
|---|---|---|
| `startDate` | CalendarDate | Day 1. Set once at onboarding. |
| `lengthDays` | number | Always `30` in v1; stored explicitly so a future change is a data question, not a code archaeology question. |
| `createdAt` | Timestamp | Audit only. |

**DayEntry**
| Field | Type | Notes |
|---|---|---|
| `date` | CalendarDate | Equals its map key; validation rejects mismatches. |
| `ratings` | object with the six indicator ids → Rating | Every id is always present; unrated values are `null`. |
| `dayType` | day-type id or `null` | Optional (FR-005). |
| `reflection` | object: `wentWell`, `lostControl`, `correctTomorrow`, `learned` — all strings (`""` when unanswered) | Optional (FR-004); never blocks saving ratings. |
| `updatedAt` | Timestamp | Audit only. |

**WeeklyReflection**
| Field | Type | Notes |
|---|---|---|
| `week` | `1..4` | Phase number; equals its map key (FR-011). |
| `text` | string | Single free-text field, distinct from daily reflections. |
| `updatedAt` | Timestamp | Audit only. |

**Settings**
| Field | Type | Notes |
|---|---|---|
| `onboardingCompleted` | boolean | Drives the first-run redirect (FR-001). |

### Explicitly not stored (derived on read)
Adherence score, day completion, day status (`today`/`completed`/`missed`/`future`), day number, phase assignment, current/best streak, overall adherence, per-indicator averages, weekly averages, trend series, and insights. All are computed by `src/domain/**` from `journey` + `entries`. Persisting any of them would create a second source of truth that can drift when a past day is edited (BR-7). This is a hard rule, not a preference.

## Storage

- **Mechanism:** `localStorage` (Web Storage), one origin, one key.
- **Key:** `kaizen.store` — a single document. Quarantine copies use `kaizen.store.corrupt.<timestamp>`; nothing else is written to the origin's storage.
- **Envelope written at that key:** `{ "schemaVersion": <int>, "savedAt": <Timestamp>, "data": <JournalDocument> }`. The version lives *inside* the value, so a schema change never requires renaming the key or leaving orphaned data behind.
- **Current `schemaVersion`: `1`.**
- **Access rule:** only `src/data/repository` reads or writes storage; it uses a thin adapter port so tests can substitute an in-memory implementation. No component, hook, or view touches `localStorage`.
- **Write semantics:** writes are whole-document, synchronous, and last-write-wins. The UI may report "saved" only after the write returns without throwing. Size is bounded by design (30 entries + 4 reflections; realistically well under 100 KB against a ~5 MB origin budget), so partial/streaming writes are unnecessary.
- **Failure modes that must be handled explicitly:** storage disabled or unavailable (Safari private mode, blocked cookies/storage) → app loads read-only with a clear warning that changes cannot be saved; quota exceeded → surfaced as a save error, prior data untouched; unparseable or shape-invalid stored value → quarantined (see below), never silently discarded.
- **Why not IndexedDB:** the data set is tiny and fully in memory; IndexedDB would add asynchronous complexity and/or a dependency with no benefit. See ADR-0001. Revisit only if the product stores blobs or many journeys.
- **Multi-tab:** out of scope for v1 behaviour guarantees. Two tabs editing simultaneously is last-write-wins. A `storage`-event listener to reload state on external change is a permitted, optional hardening, not a requirement.

## Migrations

- Every load path goes: read string → JSON parse → read `schemaVersion` → apply ordered migration steps `n → n+1` until current → validate the result against the current shape → use it. If any migration ran, the migrated document is written back immediately so the store is never left behind.
- Migration steps are pure functions over plain data, individually unit-tested with a stored fixture of the older shape. Fixtures for every historical version are kept in the test suite forever — they are the only proof that an existing user's data still upgrades.
- **Newer than supported** (`schemaVersion` > current, i.e. the user opened an older build): do **not** attempt to downgrade or coerce. Refuse to load, keep the stored value untouched, and tell the user their data was written by a newer version of the app.
- **Unrecognized/invalid shape or parse failure:** copy the raw string to `kaizen.store.corrupt.<timestamp>`, start from an empty document, and show a non-fatal error explaining that the previous data could not be read and a copy was kept. Never wipe without a quarantine copy; never crash the whole app on one bad record.
- Additive changes (new optional field with a safe default) are the preferred evolution style. A migration that drops or rewrites user content is a destructive-change decision gate and requires human approval before implementation.
- Import reuses the *same* migration and validation pipeline as load — there is exactly one upgrade code path, not a second one for files.

## Export / import format (FR-013, FR-014)

Exported file: JSON, UTF-8, suggested filename `kaizen-journal-<YYYY-MM-DD>.json`, containing `{ "app": "kaizen-journal", "schemaVersion": <int>, "exportedAt": <Timestamp>, "data": <JournalDocument> }`. The `app` marker exists so an unrelated JSON file is rejected with a clear message rather than half-applied.

Import rules: validate marker → validate `schemaVersion` (reject if newer) → migrate → validate shape → **require explicit user confirmation naming what will be replaced** → replace the whole document through the repository → reload state. Import is replace-only in v1 (no merge). A rejected or cancelled import leaves existing data byte-for-byte untouched. Round-trip must be lossless: export → import → export produces an equivalent document.

## Retention/privacy

- **Everything is personal content.** Ratings, day types, reflections, and dates describe the user's health, spiritual practice, and self-control. Treat the whole document as sensitive by default.
- **No transmission.** No journal content is sent anywhere in v1: no backend, no analytics, no error-reporting SDK, no third-party font/CDN request that could carry a referrer. This is enforced by the absence of any network client in the app (see `SECURITY.md`).
- **Retention:** data lives until the user clears browser storage, uses a private window that discards it, or imports over it. The app itself performs no automatic deletion or expiry. There is no server-side copy to delete.
- **User control:** export gives the user a complete copy; import lets them restore it. Because export produces an **unencrypted plain-JSON file**, the UI must state this plainly at the point of export — the user is responsible for where that file is stored. Encryption of the local store and of exports is explicitly out of scope for v1 (`SCOPE.md`) and parked as a future option.
- **Shared-device risk:** anyone with access to the browser profile can read the journal. This is an accepted, documented consequence of the no-account decision, not an oversight; it must not be silently "fixed" by inventing a passcode feature, which would be a scope change requiring product approval.
- **Logging:** never log journal content (reflection text, ratings) to the browser console in production paths. Error messages surfaced to the user must describe the failure, not dump the document.
