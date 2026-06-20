# AGENTS.md

## Project purpose

This repo is for exploring and eventually building an email agent / inbox assistant.

The product scope is intentionally fuzzy. The goal is to discover the smallest useful version before building too much.

## Working method

Use a Matt Pocock-style AI-assisted development workflow:

1. Start with grill-me / alignment while the idea is fuzzy.
2. Turn approved alignment into a PRD.
3. Break the PRD into small vertical slices.
4. Implement one approved bounded slice at a time.
5. Prefer test-first implementation once coding begins.
6. End major steps with a handoff summary.

Do not skip ahead in this sequence unless the founder explicitly asks.

## Scope control

Do not invent product scope.

Do not create broad architecture, large frameworks, or generic plumbing before the first useful vertical slice is clear.

Keep changes small, reviewable, and tied to the current approved step.

## Product artifacts

Use docs for durable product artifacts when needed:

- `docs/alignment.md` for the current product understanding
- `docs/prd.md` for approved requirements
- `docs/issues/` or an external tracker for vertical slices
- ADRs only for hard-to-reverse decisions

Do not create these artifacts prematurely. Create them only when the current workflow step calls for them.

## Sensitive areas

This project may eventually involve private email.

Treat the following as sensitive:

- private email content
- credentials
- OAuth
- inbox access
- sending email
- deleting email
- archiving email
- external integrations
- real-world actions on a user’s inbox

Stop and ask before doing anything involving those areas.

## Reuse-before-build

Before designing or implementing meaningful components, consider whether an existing tool, API, library, open-source project, or workflow should be reused, wrapped, or studied first.

This especially applies to:

- email parsing
- Gmail/Proton/provider integrations
- authentication
- classification
- rules engines
- scheduling
- vector search
- background jobs

Do not turn every small task into a research project, but do not build generic subsystems blindly.

## Founder approval

The founder/product lead makes final product decisions.

Ask for approval before product-scope changes, destructive actions, security-sensitive actions, external integrations, real-world email actions, or materially costly choices.

## Task summaries

At the end of repo-editing or implementation tasks, provide a plain-English summary covering:

- what changed
- key decisions
- validation performed
- risks or open questions
- recommended next step
