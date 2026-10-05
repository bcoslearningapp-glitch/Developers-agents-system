# Design Implementation Rules

Document reusable spacing, typography, component, responsive, accessibility, asset, and interaction constraints derived from approved design sources.

Source: `DES-001` (written brief, no Figma yet). These are directional constraints, not a pixel-accurate spec — implementers should exercise restraint and consistency within them.

## Tone
- Calm, minimal, disciplined, premium. Never gamified: no confetti, badges, streak-shaming copy, or urgent/red alarm styling for missed days — a missed day is shown as a plain fact.
- "Kaizen-inspired" means quiet, ordered, intentional — not literal Japanese imagery (no torii gates, bamboo, cherry blossoms, kanji-as-decoration, or zen-circle clip art).

## Color
- A restrained, mostly neutral palette: paper/off-white or near-black ground (support both a light and a dark surface), ink/graphite text, one quiet accent color used sparingly (e.g., for the current day, primary actions, and score emphasis) — not a rainbow of indicator colors.
- Status colors (completed/missed/future/today) must stay muted and desaturated, not traffic-light bright; differentiate primarily through shape/position/label, with color as reinforcement, so the UI remains usable without relying on color alone (accessibility).

## Typography
- A quiet, confident type system: one typeface family (or a restrained serif/sans pairing) with clear hierarchy through size/weight/spacing rather than decoration.
- Numbers (scores, streaks, percentages) are a first-class visual element — tabular figures, generous size for key stats on Progress.

## Layout & spacing
- Generous whitespace; a consistent spacing scale; content should breathe rather than feel dashboard-dense.
- One clear primary action per screen (e.g., "Save today's entry").

## Data visualization
- Trend charts (30-day score trend, per-indicator trends) must be calm: thin lines/bars, muted palette, no 3D/skeuomorphic chrome, no gamified milestones or badges overlaid on the chart.
- Charts must remain legible and correctly scaled on mobile widths (~360px), not just desktop.

## Motion & interaction
- Subtle, purposeful motion only (e.g., gentle transitions between days/views); no bouncy, celebratory, or attention-grabbing animation.
- Rating inputs (0–5 per indicator) must be fully keyboard-operable and have visible focus states.

## Responsive
- Single consistent visual language across desktop and mobile; mobile is not a stripped-down afterthought — all five views (Today, Progress, 30-Day Plan, Weekly Review, History) must be fully usable at mobile widths.

## Accessibility
- Sufficient contrast for the calm/muted palette (verify against WCAG AA, not just aesthetic judgment).
- Icon-only controls need accessible labels; charts need a non-color-dependent way to read status/values (e.g., text summary or labels alongside the visual).
