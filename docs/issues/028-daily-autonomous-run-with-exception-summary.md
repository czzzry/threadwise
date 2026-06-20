# Title

Daily autonomous run with exception summary

## Type

HITL

## User-visible goal

Make the current autonomous labeling workflow operational by providing one command that fetches a fresh batch, auto-applies all current suggested labels, removes `INBOX` for low-value and promotional mail, and prints the remaining unlabeled exceptions for inspection.

## Scope

- Add a single CLI for one-account daily autonomous execution
- Fetch a new live Gmail batch
- Auto-apply all current suggested labels for the fetched batch
- Remove `INBOX` only for `spam-low-value` and `promotions`
- Print a compact post-run summary including:
  - fetched batch id
  - fetched count
  - applied label writes
  - applied `INBOX` removals
  - count of remaining unlabeled exceptions
  - sender/subject lines for remaining unlabeled exceptions

## Non-goals

- Background scheduling or polling
- Multi-account orchestration
- New Gmail actions beyond current label write-back and bounded `INBOX` removal
- Solving the unlabeled exceptions themselves

## Acceptance criteria

- One command can fetch and process a fresh batch end to end
- When no new messages exist, the command exits cleanly without side effects
- When a new batch exists, suggested labels are auto-applied and low-value/promotional mail is removed from `INBOX`
- The command prints the remaining unlabeled exceptions clearly for manual follow-up

## Expected tests or verification

- Test the daily-run CLI exits cleanly when no new messages are found
- Test the daily-run CLI fetches a batch, auto-applies suggested labels, and reports unlabeled exceptions
- Re-run the relevant fetch, auto-apply, Gmail-writer, and status-related suites
