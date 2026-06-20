# Title

Improve first-time real-human personal detection

## Type

HITL

## User-visible goal

Reduce missed personal messages from real people when the sender is not yet in the trusted personal sender store.

## Scope

- Tighten the local classifier only
- Improve detection for direct person-to-person messages routed through platform wrappers such as LinkedIn messaging digests
- Improve detection for person-to-person file/folder share notifications routed through Google Drive / Google Sheets
- Keep job alerts, platform growth nudges, and generic digests out of `personal`
- Preserve the existing trusted-sender store behavior; this slice should improve first-time suggestions before trust has been learned

## Non-goals

- Broad contact graph inference
- Multi-message conversation threading
- New Gmail mutation behavior
- A broad relationship model or profile store

## Acceptance criteria

- Direct LinkedIn message digests like `Kirth just messaged you` surface `EA/Personal`
- Human Google Drive / Sheets share notifications like `Folder shared with you` surface `EA/Personal`
- LinkedIn job alerts and generic platform updates do not surface `EA/Personal`
- Existing trusted-sender behavior continues to work

## Expected tests or verification

- Test LinkedIn direct-message digests classify to `personal`
- Test Google Drive / Sheets share notifications from a real human classify to `personal`
- Test LinkedIn job alerts do not classify to `personal`
- Re-run the relevant classifier, fetcher, stored-batch, and local-browser test suites
