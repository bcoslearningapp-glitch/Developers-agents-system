# Integrations

## External systems

**None. Kaizen v1 has no external systems.**

There is no backend service, no database server, no third-party API, no authentication provider, no analytics or telemetry service, no error-reporting service, no push/notification service, no payment provider, and no CDN-hosted runtime asset. `FR-015` and `agent/product/SCOPE.md` forbid a backend for core functionality, and `NON_FUNCTIONAL.md` forbids any journal content leaving the device.

Consequently the application ships **no network client at all**: no `fetch`/`XMLHttpRequest`/`WebSocket`/`EventSource` calls, no remote fonts or stylesheets, no tracking pixels, and no third-party `<script>` tags. Fonts and every other asset are self-hosted in the bundle. The only I/O boundaries the app has are:

| Boundary | Direction | Nature |
|---|---|---|
| `localStorage` (same origin) | read/write | Local browser storage — see `agent/architecture/DATA.md`. |
| File download (export) | out | A JSON Blob saved by the user to their own filesystem. Local only; no upload. |
| File input (import) | in | A user-selected local file read in the browser. Local only; no upload. |
| Static file host (page load) | in | Serving the app's own HTML/JS/CSS. Not a runtime integration and carries no journal data. |

The static host that serves the bundle is infrastructure, not an integration: it never receives, stores, or observes journal content, because journal content never leaves the browser.

Any proposal to add a real integration (sync, accounts, backup service, analytics, crash reporting, AI-generated insights via an API) changes the product's privacy posture and/or scope and is a **human decision gate** under `AGENTS.md`. It must not be introduced as an implementation detail.

## Contracts/failure modes

No external contracts exist, so there are no API schemas, versioning agreements, rate limits, retries, timeouts, circuit breakers, or vendor SLAs to design against. The failure modes that would normally live here belong to local I/O instead and are specified in `agent/architecture/DATA.md`:

- storage unavailable (private mode / storage blocked) → app loads read-only with an explicit warning;
- quota exceeded on write → save reported as failed, existing data untouched;
- corrupt or unreadable stored document → quarantined copy, empty start, visible non-fatal message;
- stored/imported `schemaVersion` newer than supported → refuse to load, do not coerce;
- invalid or non-Kaizen import file → rejected with a clear message, existing data untouched.

Because there is no network dependency, the app is fully functional offline once loaded. (An installable offline PWA is a separate, out-of-scope feature — `SCOPE.md`.)

## Cost/credential notes

- **Recurring cost: none.** No paid service, subscription, cloud resource, API spend, or per-seat licensing is used or planned for v1. All build/test tooling is free OSS (see ADR-0001).
- **Credentials: none.** The application has no API keys, tokens, secrets, or service accounts. There is nothing to put in a `.env` file, and no `.env` is expected in this repository. If a future task appears to need a secret, that is a signal the change crosses a decision gate — stop and escalate rather than introducing one.
- **Hosting:** the build output is plain static files deployable to any static host (GitHub Pages is the reference target, free tier). Choosing that target costs nothing and creates no lock-in; **actually performing a production deployment, or activating a domain/DNS or billing, remains a human decision gate** and is deferred to milestone M7.
