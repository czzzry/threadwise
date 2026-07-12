# Local artifact inventory and retention report

Status: Follow-up candidate
Type: Implementation
GitHub issue: `#18`
Parent: GitHub issue `#15`; `docs/local-data-retention-and-inbox-freshness-review-2026-07-01.md`

## What to build

Add a read-only local artifact inventory command that reports what Threadwise is storing locally without printing private email content.

The command should classify artifacts by retention class: raw message content, compact metadata, reports, feedback/rules/memory, audit/action state, usage ledger, and credentials presence.

## Acceptance criteria

- [ ] Reports artifact counts and total byte sizes by class.
- [ ] Reports oldest/newest modified timestamps by class.
- [ ] Reports batch counts, report counts, and action-audit counts.
- [ ] Detects likely body-bearing artifacts by schema/key names without printing body values.
- [ ] Reports credential directory existence without listing or reading credential file contents.
- [ ] Emits JSON output suitable for dashboard or later cleanup tooling.
- [ ] Has tests using temporary synthetic artifacts only.

## Safety boundaries

- Must not read live Gmail.
- Must not inspect private credential contents.
- Must not print message bodies, snippets, subjects, senders, OAuth tokens, or file contents by default.
- Must not delete or modify files.

## Parallelization

Can run in parallel with `095`. Can run in parallel with `094` if that slice uses isolated files and fake clients in tests.
