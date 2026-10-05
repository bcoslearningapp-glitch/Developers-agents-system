# Quality Gates

Apply gates proportionally, but every applicable mandatory gate must pass before a Reviewer returns PASS.

Gates apply identically regardless of which implementation worker model executed the task. A dispatch to a smaller/local worker is reviewed exactly as strictly as one to a larger cloud worker—no gate is relaxed because the executing model has less capacity. If a task is too large for the selected profile, split it into smaller atomic tasks instead of accepting a lower bar.

## Universal
- Requirements/acceptance criteria are traceable to the task.
- No changes outside `Allowed paths`.
- No unresolved Critical/High review findings.
- Build/compile succeeds where applicable.
- Type/static checks succeed where applicable.
- Lint/format checks succeed where applicable.
- Relevant automated tests pass.
- Error paths and edge cases are handled.
- No secrets/credentials are committed or exposed.
- New dependencies are necessary, compatible, and justified.
- No silent scope expansion.
- Existing unrelated behavior is not knowingly broken.

## Web UI
- Approved design intent and component conventions are followed.
- Responsive behavior is verified for required breakpoints.
- Keyboard navigation/focus behavior is correct where interactive.
- Semantic HTML/ARIA and contrast/accessibility requirements are addressed.
- Loading, empty, error, disabled, and success states exist when relevant.
- Critical user flow is verified beyond isolated unit tests.
- Performance regressions are considered for significant UI/data changes.

## Mobile
- Required platform/build succeeds.
- Navigation/back/deep-link behavior is correct when relevant.
- Safe area, keyboard, orientation/device-size behavior is addressed.
- Permissions are least-privilege and failure/denial is handled.
- Secure storage is used for sensitive tokens/data.
- Offline/network interruption/error states are handled when relevant.
- Accessibility labels/focus/touch targets are checked.

## Backend/API
- Input validation and output contracts are explicit.
- Authentication and authorization are checked at the correct boundary.
- Rate/abuse/failure behavior is considered where exposed externally.
- Database changes include safe migration/rollback considerations.
- Logging avoids secrets/sensitive payload leakage.
- Timeouts/retries/idempotency are handled where relevant.

## Security-sensitive work
- Threat/trust-boundary impact reviewed.
- Dependency/supply-chain exposure reviewed.
- Secrets remain out of repository/model context.
- Privilege boundaries and data access are tested.
- Any policy-changing decision has an approved decision record.
