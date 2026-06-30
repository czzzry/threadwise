# MVP+1 Portfolio Demo Alignment

Status: Aligned next-phase direction, not yet an implementation PRD
Current as of: 2026-06-30
Depends on: closing and committing the Gmail MVP release state
Builds on: `docs/prd.md`, `docs/v2-alignment.md`, `docs/portfolio.md`

## Purpose

MVP+1 should make Threadwise recruiter-ready as a portfolio artifact.

The goal is not to broaden automation scope first. The goal is to make the existing Gmail-first product legible, polished, and credible to a recruiter or hiring manager within the first few minutes of seeing the repo.

## Positioning

Threadwise should present the founder as an AI product engineer / product-minded full-stack builder.

The demo and README should emphasize:

- product clarity first, with technical depth one click deeper
- human-in-the-loop AI automation
- real Gmail usage with synthetic data
- explicit safety boundaries before broader inbox action
- polished product judgment, not just backend tooling

## Demo Direction

Use real Gmail UI with a demo Gmail account seeded only with synthetic emails.

The public/demo assets should state clearly:

> Demo uses a Gmail test account populated with synthetic emails. No private inbox data is shown.

The demo should show Threadwise operating inside Gmail, not a fake email server. The demo may include polished overlay captions, but it must not imply capabilities that do not exist.

## MVP+1 Phases

1. Close MVP git state.
   - Review the current dirty diff.
   - Commit real Gmail MVP closeout changes.
   - Ignore or remove generated local artifacts.
   - Reconcile stale issue/doc status.

2. Design review and aesthetic direction.
   - Audit the current Gmail companion sidebar, daily dashboard, teach flow, and unsubscribe flow.
   - Identify what can be changed visually versus what is constrained by Gmail.
   - Propose 2-3 aesthetic directions.
   - Select one direction.
   - Implement the chosen aesthetic.
   - Iterate until the capture surfaces are portfolio-ready.

3. Demo script.
   - Write `docs/demo-script.md`.
   - Define exact short GIF/video flows:
     - daily briefing/report
     - teach the agent safely
     - unsubscribe with approval
   - Define a roadmap micro-clip:
     - Gmail to ProtonMail to Outlook/Hotmail, clearly labeled as "Next" or "Roadmap."

4. Seed demo Gmail account.
   - Use synthetic emails only.
   - Make categories obvious enough for a fast product demo.
   - Avoid private, sensitive, or misleading content.

5. Capture assets.
   - Produce 3 short GIFs, each roughly 10-20 seconds max.
   - Optionally produce higher-quality MP4 versions.
   - Produce static screenshots.
   - Store committed public assets under `docs/assets/`.

6. README and portfolio packaging.
   - Put the GIFs near the top of `README.md`.
   - Add concise captions and the synthetic-data disclaimer.
   - Keep technical architecture and safety details below the fold.
   - Update `docs/portfolio.md` to match the final demo story.

7. Interactive demo path.
   - Keep this secondary to the README assets.
   - Provide a low-friction way to replay or inspect the demo locally if useful.

8. Close MVP+1.
   - Run relevant tests and smoke checks.
   - Commit all UI, docs, demo assets, and README changes.
   - Confirm clean `git status`.
   - Push.
   - Optionally tag the repo as the recruiter-ready demo milestone.

## Design Review Scope

The design review is intentionally bracketed as its own phase because it may need several passes.

Questions to answer before capture:

- What is the maximum useful extent of visual changes to the Threadwise sidebar?
- What parts of the presentation are constrained by Gmail?
- What aesthetic best communicates polished AI product judgment?
- How can the sidebar, dashboard, teach flow, and unsubscribe flow look cohesive in a short demo?

The working aesthetic direction to explore first is:

> Calm AI operator.

This should mean:

- compact but premium information density
- restrained color and strong hierarchy
- clear status pills for classification and handling
- a prominent but calm impact-preview panel
- obvious confirmation choices
- no loud SaaS gradients or decorative visuals that fight the Gmail surface

The portfolio demo may look slightly slicker than the raw internal product, as long as it stays truthful to actual implemented behavior.

## Process Reminder

The repo workflow for this kind of phase is:

1. Grill / align while the idea is fuzzy.
2. Document the aligned direction.
3. Convert the approved direction into a bounded PRD.
4. Break the PRD into small vertical slices.
5. Triage the next slice until it is implementation-ready.
6. Implement one approved bounded slice at a time, preferably test-first.
7. End major steps with a handoff and current-state doc updates.

This document completes step 2 for MVP+1. The next planning step, after MVP git closeout, is a bounded PRD for the design-review and demo-packaging work.
