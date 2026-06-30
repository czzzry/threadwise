# Status

Completed
Current as of: 2026-06-30
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/issues/068-mvp-plus-one-design-review-and-aesthetic-direction.md`

# Title

Build the demo script and synthetic Gmail seed plan

## Type

Product / Demo planning

## Blocked by

- `docs/issues/068-mvp-plus-one-design-review-and-aesthetic-direction.md`

## User stories covered

`3`, `4`, `5`, `6`, `7`, `8`, `9`, `27`, `28`, `29`, `30`, `31`, `32`, `33`, `34`, `35`, `36`, `39`, `43`

## What to build

Create the exact demo script and synthetic Gmail seed plan for the MVP+1 recruiter demo.

The output should define the three primary short GIF/video flows and the optional roadmap micro-clip. It should also specify the synthetic emails needed in the demo Gmail account so capture can happen safely and consistently.

This slice should make the capture work deterministic enough that the next slice can follow the script rather than inventing the story during recording.

## Acceptance criteria

- [x] `docs/demo-script.md` defines the three 10-20 second primary demo flows.
- [x] The daily briefing/report flow shows categorized email and what happened today.
- [x] The teach flow shows selected email context, correction, impact preview, and explicit human choice.
- [x] The unsubscribe flow shows unsubscribe availability and approval/review behavior without implying autonomous unsubscribe.
- [x] The optional roadmap micro-clip is clearly labeled as "Next" or "Roadmap."
- [x] The synthetic Gmail seed plan lists realistic fake emails, sender names, subjects, snippets, and intended categories.
- [x] The plan explicitly excludes private email, sensitive content, credentials, and unsafe real-world actions.
- [x] The plan includes caption text for each GIF/video.

## Output

- `docs/demo-script.md`
- Synthetic Gmail seed plan
- Capture safety checklist

## Boundaries

- Do not capture final assets in this slice.
- Do not modify product UI in this slice unless needed to clarify script assumptions.
- Do not use private inbox data.
- Do not perform real unsubscribe/delete/archive/send actions.

## Completion note

Completed in `docs/demo-script.md`.

The script defines:

- three primary 10-20 second flows
- optional roadmap micro-clip labeled as future scope
- exact overlay captions
- 24 synthetic Gmail seed messages
- capture safety checklist

Validation:

- reviewed acceptance criteria coverage against this issue
- checked copy for synthetic-data, roadmap, and unsafe-action boundaries
