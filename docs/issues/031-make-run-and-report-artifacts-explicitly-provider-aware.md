# Title

Make run and report artifacts explicitly provider-aware

## Type

HITL

## User-visible goal

Prepare the product for one user across Gmail and ProtonMail by making run and report artifacts explicitly identify the inbox provider, while preserving the current single-inbox Gmail workflow.

## Scope

- Extend the current stored batch and report artifacts to carry an explicit provider field
- Start with Gmail as the only live provider value
- Ensure daily and weekly reports retain account id and provider identity
- Keep the current autonomous Gmail workflow behavior unchanged
- Avoid introducing a broad provider framework; just make the workflow artifacts provider-aware

## Non-goals

- ProtonMail live integration
- Cross-inbox merged processing
- Multi-user support
- New Gmail actions
- Generic abstraction work beyond what this slice requires

## Acceptance criteria

- New stored batches can record the provider explicitly
- Daily reports can record the provider explicitly
- Weekly reports can record the provider explicitly
- Existing Gmail workflows continue to run with no behavior change other than the new metadata
- Existing local inspection/reporting tools continue to work

## Expected tests or verification

- Test fetched Gmail batches persist provider metadata
- Test daily reports include provider metadata
- Test weekly reports include provider metadata
- Re-run the relevant fetch, report, and status-related suites
