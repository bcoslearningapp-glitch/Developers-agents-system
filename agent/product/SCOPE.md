# Scope

## In scope
- Everything in `agent/product/PRD.md` functional requirements FR-001–FR-016: onboarding, 30-day/4-phase structure, daily indicator rating + scoring, daily reflection, day type classification, Today, Progress, 30-Day Plan, Weekly Review, History, export/import, local-only persistence, responsive desktop + mobile UI.

## Explicitly out of scope
- User accounts, sign-in, or any authentication/authorization.
- Backend service, server-side storage, or multi-device sync.
- Notifications/reminders (push, email, or otherwise).
- Sharing, social, or collaboration features of any kind.
- User-customizable/extensible indicator set or day-type list (both are fixed lists in v1).
- Multiple concurrent or historical journeys; starting a second 30-day journey after completing/abandoning the first.
- Localization / multi-language support (English only).
- Native mobile apps (responsive web only).
- Data encryption of the local store or the exported file.
- Analytics/telemetry that transmits journal content off-device.

## Future / parking lot
- Offline-installable PWA.
- User-defined custom indicators and/or custom day types.
- Local reminders/notifications (still no backend).
- Support for multiple journeys / restarting and comparing past journeys.
- Optional passphrase-based encryption for the local store and/or export file.
- Theming (e.g., dark mode) beyond the single calm/minimal visual system.
