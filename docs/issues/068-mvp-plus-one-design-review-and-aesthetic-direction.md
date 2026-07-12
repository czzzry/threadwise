# Status

Completed
Current as of: 2026-06-30
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/mvp-plus-one-portfolio-demo-alignment.md`

# Title

Run the MVP+1 design review and choose the Threadwise portfolio aesthetic

## Type

Design / Product

## User stories covered

`21`, `22`, `23`, `24`, `25`, `26`, `41`, `42`, `44`

## What to build

Produce a reviewable design direction for the recruiter-ready Threadwise demo before any screenshot/video capture work begins.

This slice should audit the current Gmail companion sidebar, daily dashboard, teach flow, and unsubscribe review/handoff surfaces. It should define what can realistically be changed inside Threadwise-controlled UI, what remains constrained by Gmail, and what aesthetic should guide the MVP+1 portfolio pass.

The output should be specific enough for the next implementation slice to apply the chosen aesthetic without reopening broad product questions.

## Acceptance criteria

- [x] The current Threadwise demo/capture surfaces are audited for visual strengths, weaknesses, and capture risks.
- [x] The review distinguishes full-control, partial-control, and constrained-by-Gmail areas.
- [x] The review proposes 2-3 aesthetic directions for the portfolio demo.
- [x] Each direction includes concrete implications for layout, color, type scale, status treatments, action hierarchy, and demo captions.
- [x] The recommendation identifies one preferred aesthetic direction.
- [x] The review includes a concrete implementation checklist for the chosen direction.
- [x] The review calls out any risks where a slicker portfolio UI could overstate implemented behavior.
- [x] The founder can approve, reject, or annotate the design direction before implementation.

## Output

- Reviewable design artifact or document.
- Chosen aesthetic recommendation.
- Implementation checklist for the next slice.

## Boundaries

- Do not capture final README GIFs or screenshots in this slice.
- Do not seed the Gmail demo account in this slice.
- Do not change product scope or add new inbox actions.
- Do not redesign Gmail itself.

## Completion note

Completed with founder approval of the warm ink-and-paper Threadwise redesign direction.

Design references:

- `docs/design ideas/Threadwise_design.html`
- `docs/design ideas/threadwise logo.png`

Follow-on logo handling is nested into later slices rather than split into a standalone issue:

- `069`: extract/use the square app icon in the product/demo UI aesthetic.
- `072`: make the primary logo prominent in README, portfolio, and promo assets.
