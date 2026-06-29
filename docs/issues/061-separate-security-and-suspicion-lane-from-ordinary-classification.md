# Status

Current
Current as of: 2026-06-28
Triage state: `ready-for-agent`
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

- [ ] A stored-corpus path can mark messages as security-sensitive or suspicious separately from ordinary inbox taxonomy labels.
- [ ] The resulting artifacts make it obvious which messages require caution rather than normal categorization.
- [ ] The slice does not broaden live inbox mutation scope.

