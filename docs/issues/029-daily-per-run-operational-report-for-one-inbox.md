# Title

Daily per-run operational report for one inbox

## Type

HITL

## User-visible goal

After each autonomous inbox run, produce a compact daily report for that inbox showing how many emails were processed and what happened to them.

## Scope

- Add a durable per-run report artifact for one inbox run
- Base the report on the existing daily autonomous run workflow
- Report one inbox at a time
- Capture:
  - inbox/account id
  - batch id
  - total emails processed
  - counts by final label
  - how many were auto-labeled
  - how many had `INBOX` removed
  - how many remained unlabeled
  - the sender/subject lines for the remaining unlabeled exceptions
- Keep the report local and privacy-conscious

## Non-goals

- Weekly rollups
- Cross-inbox combined reporting
- ProtonMail integration
- New Gmail actions
- Rich dashboard UI

## Acceptance criteria

- A daily autonomous run for one inbox produces a durable local report artifact
- The report reflects the actual run outcomes for fetched count, label counts, auto-applied count, `INBOX` removals, and unlabeled exceptions
- The report can be regenerated or inspected locally without hitting Gmail again
- The report does not dump full private email bodies by default

## Expected tests or verification

- Test that a daily run writes a local report artifact with the expected summary fields
- Test that unlabeled exceptions are included in the report in sender/subject form only
- Re-run the relevant daily-run, status, and summary-related suites
