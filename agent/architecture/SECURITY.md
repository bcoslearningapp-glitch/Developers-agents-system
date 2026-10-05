# Security Architecture

Kaizen v1 is a local-only client application: one user, one device, one browser profile, no server, no accounts, no credentials, no network traffic carrying user data. That removes most of a typical application's attack surface (no auth, no session, no API, no injection into a database, no server-side secrets) and concentrates the remaining risk in three places: **the browser origin, the local store, and untrusted input that the user imports.**

## Trust boundaries

| # | Boundary | Trusted side | Untrusted side | Control |
|---|---|---|---|---|
| B1 | The browser origin serving the app | The app's own bundle | Any other origin/site | Browser same-origin policy; `localStorage` is origin-scoped. Do not weaken with permissive CORS or `postMessage` listeners (none are needed). |
| B2 | The device / OS user account | The app running in that profile | Anyone else with physical or profile access | **None available by design.** Data is readable by anyone with access to the browser profile. Accepted and documented (see Sensitive data). |
| B3 | The local store (`localStorage`) | The repository layer | The stored bytes themselves | Stored JSON is treated as untrusted input on every read: parse defensively, validate shape, quarantine on failure (`DATA.md`). |
| B4 | Imported file | The repository layer | Any file the user selects | Full validation before use: app marker, `schemaVersion`, structural shape, field types/ranges; explicit user confirmation before replacing data (FR-014). |
| B5 | The static host serving the bundle | — | Host/CDN operator, network path | HTTPS-only hosting; self-hosted assets only (no third-party scripts/fonts) so no external party can inject code into the origin. |

There is deliberately **no** boundary for "server", "API", "tenant", or "role" — those do not exist in this product.

## Authentication/authorization

**None, by product design.** `FR-015` and `agent/product/SCOPE.md` exclude accounts, sign-in, and any authentication/authorization. There is one user, no roles, no multi-tenancy, no privileged operations, and no server to authorize against. All data in the store belongs to the single local user.

Implications that must be respected rather than "improved":
- Do not introduce a passcode/PIN/lock screen, biometric gate, or "encrypt my journal" feature as an implementation detail. It would change product scope and privacy posture and is a **human decision gate** (`AGENTS.md`). Optional passphrase encryption is already parked in `SCOPE.md` as a future item.
- Do not add any identity provider, device fingerprint, or user id — there is nothing to identify.
- Because there is no authorization boundary, there is also no place to leak one: the security review of any task should confirm no auth/identity concept crept in.

## Sensitive data

**Classification: all journal content is personal and sensitive.** Ratings cover sleep, spiritual practice, eating, movement, and self-control; reflections are free-text personal confessions of where the user lost control. Combined with dates, this is exactly the kind of data that must not be casually transmitted, logged, or exported without the user knowing.

Handling rules:
1. **Never transmits.** No network client exists in the app (`INTEGRATIONS.md`). No analytics, telemetry, crash reporting, remote font, or CDN asset in v1. Adding one is a decision gate.
2. **Never logged.** Reflection text and ratings must not be written to `console` in production paths; error messages describe the failure, never dump the document.
3. **Never in the repository.** No fixture, screenshot, seed file, or test data may contain the real user's journal content. Test fixtures use obviously synthetic text.
4. **Export is unencrypted plain JSON.** This is an accepted, scoped decision (`SCOPE.md` excludes encryption). The product **must** disclose this in-product at the point of export: the file is a complete, readable copy of the journal and the user is responsible for storing it safely. Silent export without that disclosure is a review failure, not a copy nitpick.
5. **The local store is unencrypted.** Anyone with access to the browser profile (shared computer, unlocked device, browser sync to another machine, forensic access to disk) can read it. Documented as a known residual risk (B2) — not mitigated in v1.
6. **No secrets exist.** The app has no API keys or tokens; nothing belongs in a `.env`. A task that seems to need a secret is a signal to escalate, not to add one.
7. **Deletion.** There is no server copy; clearing browser data removes the journal irreversibly. Any in-app "reset/clear data" affordance must require explicit confirmation and say plainly that it cannot be undone.

## Threats/controls

| ID | Threat | Likelihood/impact | Controls |
|---|---|---|---|
| T1 | **XSS / script injection** — the user's own reflection text (or an imported file's strings) rendered as markup, giving an attacker script execution in the origin and read access to the entire local store. This is the single highest-severity technical risk in the app. | Low likelihood, high impact | Render all user text as text nodes through React's default escaping. **Ban `dangerouslySetInnerHTML`, `eval`, `new Function`, and dynamic `<script>`/`<style>` injection** anywhere in the codebase (`STACK.md` constraint; enforced in review). No markdown/HTML rendering of user content in v1. No `innerHTML` in owned SVG/chart code. |
| T2 | **Malicious or malformed import file** — crafted JSON causing crashes, prototype pollution (`__proto__`/`constructor` keys), enormous payloads, or silently corrupted state. | Medium likelihood (user error), medium impact | Validate before use at B4: app marker, `schemaVersion` (reject newer), structural shape, key whitelist, field types, rating range `0..5`, date format, phase keys `1..4`; build the resulting object from validated fields rather than spreading raw parsed input; ignore unknown keys; enforce a sane maximum file size; reject non-JSON. Explicit user confirmation before replacing data. Failed import must leave existing data untouched. |
| T3 | **Silent data loss / destruction** — an import, migration, or reset wiping the journal without the user understanding. | Medium likelihood, high impact (irreplaceable data) | Confirmation step naming what will be replaced; quarantine copy before discarding an unreadable store; migrations never drop content without an approved decision; export available at any time; write-then-confirm save semantics (`DATA.md`). |
| T4 | **Supply-chain compromise** — a malicious or compromised npm package exfiltrating the store at runtime. | Low likelihood, high impact | Minimal runtime dependency surface (React only — ADR-0001); no runtime dependency may perform network I/O; new runtime dependencies require an ADR; committed lockfile with `npm ci`; prefer established, widely-used packages; keep charting/routing/date logic in-house rather than importing small unvetted packages. |
| T5 | **Third-party content in the origin** — remote fonts, CDN scripts, or embedded widgets able to read `localStorage` or leak referrer data. | Low likelihood, high impact | Self-host every asset. No third-party runtime resources of any kind. |
| T6 | **Shared/unattended device access** to the browser profile. | Medium likelihood, medium impact | Not mitigated in v1 by design (no auth in scope). Documented residual risk; the export-is-unencrypted disclosure raises user awareness. Revisit only via the parked encryption/passphrase item. |
| T7 | **Exported file mishandled** by the user (cloud sync, email, shared downloads folder). | Medium likelihood, medium impact | In-product disclosure at export (see Sensitive data #4); dated, unambiguous filename so stale copies are recognizable. |
| T8 | **Clickjacking / framing** of the app by a hostile page. | Low likelihood, low impact | Low value target (no privileged actions, no auth), but set framing/`X-Frame-Options`/CSP `frame-ancestors` protections where the chosen static host allows headers. |
| T9 | **Storage tampering** — the store edited by hand or by another script in the origin, producing invalid state. | Low likelihood, low impact | Same defensive read/validation path as T2 (B3): invalid state is quarantined, not trusted; the app must not crash on a bad record (`NON_FUNCTIONAL.md` observability). |

### Recommended hardening (implement when the shell and hosting are in place)
- Ship a restrictive **Content-Security-Policy** consistent with a no-third-party, no-inline-script bundle (`default-src 'self'`; no `unsafe-eval`; `connect-src 'none'` if the host permits headers, otherwise via `<meta http-equiv>` with its documented limitations). A CSP that blocks `connect-src` is also a useful *enforcement* of the "no journal content leaves the device" promise, not just a mitigation.
- `referrer-policy: no-referrer`, HTTPS-only hosting, and no `target="_blank"` without `rel="noopener noreferrer"`.
- Treat these as tasks in M6/M7, verified in the release checklist — not as optional polish.

### Security review checklist for every task
- No new network call, dependency with network capability, or third-party asset.
- No raw HTML rendering of user or imported content.
- Any new input path validates shape and range at the boundary.
- No journal content in logs, fixtures, commit messages, or reports.
- No secret, token, or `.env` introduced.
- No auth/identity concept introduced.
- Destructive operations require explicit user confirmation.
