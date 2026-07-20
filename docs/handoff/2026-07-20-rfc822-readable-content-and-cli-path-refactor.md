# RFC822 Readable Content and CLI Path Refactor Handoff

Status: Completed bounded refactors
Current as of: 2026-07-20
Builds on: `CONTEXT.md`, `docs/v2-alignment.md`, and the architecture review requested on 2026-07-20

## Outcome

Threadwise now has one deep RFC822 readable-content module shared by the live ProtonMail and Outlook IMAP adapters. It owns MIME traversal, charset decoding, HTML-to-text extraction, non-readable element suppression, malformed-markup recovery, whitespace shaping, and optional output limits.

Provider behavior remains explicit:

- ProtonMail keeps its full readable body.
- Outlook keeps its existing eight-line and 1,200-character limits.
- No transport, credential, mailbox, label, or provider-write behavior changed.

The refactor preserved and relocated the existing uncommitted Proton HTML hardening. Outlook now receives the same script/style/template/noscript suppression, fixing previously demonstrated parser drift.

As an adjacent bounded cleanup, twelve command modules now use the existing `cli_paths` module. Their duplicated private path-resolution helpers were removed.

## Validation

- Red tests first proved the missing shared parser and Outlook script/style leakage.
- A second red test proved nested markup with a void element could strand the HTML parser in ignored state.
- `72` focused parser, provider-client, and command tests pass.
- `718` repository-wide unit tests pass.
- Python compilation and diff whitespace checks pass.

All validation used fixtures and fake clients. No live inbox, credentials, or provider mutation was accessed.

## Risks and follow-up

- Gmail uses a provider-specific payload format rather than RFC822 `Message` objects, so its separate body extractor was intentionally left alone.
- The broader Gmail companion rendering and local-artifact candidates remain unapproved follow-up architecture work.
- The working tree contained substantial unrelated founder changes before this task; they were preserved and not staged or committed.
