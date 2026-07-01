# Status

Completed
Current as of: 2026-06-28
Triage state: `completed`
GitHub issue: `#5`
Builds on: `docs/prd.md`, `docs/issues/060-build-memory-first-runtime-cascade-prototype-on-stored-corpora.md`

# Title

Separate security and suspicion lane from ordinary classification

## Type

AFK

## Blocked by

- `docs/issues/060-build-memory-first-runtime-cascade-prototype-on-stored-corpora.md`

## User stories covered

`11`, `13`, `20`, `21`

## What to build

Define and prototype a distinct safety lane for phishing, suspicious account mail, and other security-sensitive messages so that they are not handled as ordinary category decisions.

This slice should stay bounded:

- classify or flag stored examples into a security-sensitive lane
- preserve explicit uncertainty when the system is not confident
- avoid promising full phishing detection or broad autonomous action

## Acceptance criteria

- [x] A stored-corpus path can mark messages as security-sensitive or suspicious separately from ordinary inbox taxonomy labels.
- [x] The resulting artifacts make it obvious which messages require caution rather than normal categorization.
- [x] The slice does not broaden live inbox mutation scope.

## Implemented

- Runtime cascade outcomes include `risk_state`, `safety_lane`, and `requires_caution`.
- Provider reports include `safety_reviews`, `safety_review_count`, and security/suspicious counts.
- Safety disposition artifacts remain local review memory and do not mutate live providers.

Completed in repo before GitHub issue closeout sync on 2026-07-01.
