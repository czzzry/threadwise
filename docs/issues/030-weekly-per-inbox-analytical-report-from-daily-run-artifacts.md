# Title

Weekly per-inbox analytical report from daily run artifacts

## Type

HITL

## User-visible goal

Produce a weekly report for one inbox that summarizes the previous full week using the stored daily run reports, so the user can understand trends, dominant categories, and exception rate without reprocessing raw Gmail data.

## Scope

- Read the existing daily run report artifacts from `data/gmail_fetch/reports/`
- Build a weekly report for one inbox/account at a time
- Base the report on the previous full 7-day window of available daily artifacts
- Include:
  - inbox/account id
  - covered date window
  - total processed email count
  - total auto-applied count
  - total `INBOX` removal count
  - total unlabeled count
  - aggregate label counts
  - exception rate
  - largest categories
  - simple trend view across the included daily runs
- Keep the report local and privacy-conscious

## Non-goals

- Cross-inbox combined reporting
- Provider comparison
- Fetching or mutating Gmail during report generation
- Rich dashboard UI
- Unsubscribe execution

## Acceptance criteria

- A weekly report can be generated from existing daily report artifacts without hitting Gmail
- The report reflects the previous full week for one inbox
- The report highlights totals, biggest categories, and exception rate clearly
- The report does not include full private email bodies by default

## Expected tests or verification

- Test weekly report generation from multiple daily report artifacts for one inbox
- Test that aggregate counts and exception rate are calculated correctly
- Test that the report uses sender/subject-level exception references only if any detail examples are included
- Re-run the relevant daily-report and summary-related suites
