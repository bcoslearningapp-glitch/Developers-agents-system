# Non-Functional Requirements

## Security and privacy
- No journal content leaves the device in v1: no backend calls, no third-party analytics/trackers that receive ratings, reflections, or dates.
- Export files are plain JSON; product copy must disclose they are unencrypted local backups the user is responsible for.
- Import must require explicit confirmation before overwriting existing local data and must validate file shape before applying it.

## Performance
- Daily entry save and navigation between the five views must feel instant (local-only, no network round trip).
- All aggregate computations (streaks, averages, trends, insights) run client-side over at most 30 day-records plus 4 weekly reflections — negligible load; no pagination or heavy computation infrastructure needed.

## Availability / reliability
- No data loss on refresh, tab close, or browser restart: every save must be durably persisted before being reflected as "saved."
- The local storage schema must be versioned so future changes can migrate existing users' data without loss.

## Accessibility
- Target WCAG 2.1 AA where applicable: full keyboard operability for rating inputs, day selection, and navigation; visible focus states; sufficient color contrast within the calm/minimal palette; semantic structure and labels for screen readers, including icon-only controls.

## Browser/device/platform support
- Latest evergreen desktop and mobile browsers (Chrome, Safari, Firefox, Edge).
- Responsive from ~360px mobile viewport width through common desktop widths; no horizontal scrolling of the page shell at any supported width.

## Localization
- English only in v1 (see `SCOPE.md`).

## Observability
- No backend, so no server-side observability in v1. Client-side error handling must degrade gracefully (e.g., a corrupted local record must not crash the whole app) and surface a clear in-app message rather than a silent failure.

## Maintainability / testing
- Business logic (score calculation, phase mapping, streaks, day status, insight rules) must be unit-tested independently of UI.
- Critical user flows (onboarding, daily entry save, export, import with confirmation) must have flow-level/component tests.
- Prefer a typed codebase and static checks (type-check + lint) as part of the required quality gates.
