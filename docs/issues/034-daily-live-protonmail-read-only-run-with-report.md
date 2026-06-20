# Title

Daily live ProtonMail read-only run with report

## Type

HITL

## User-visible goal

Run a bounded daily ProtonMail workflow that fetches a live batch through Bridge, classifies it into the existing local batch model, and writes a durable daily report, without performing any write or inbox-mutation actions on the Proton account.

## Scope

- Add a daily live ProtonMail run command
- Reuse the existing provider-aware local batch model
- Keep provider-side behavior read-only
- Write a durable per-run ProtonMail daily report
- Preserve compatibility with the existing weekly reporting seam

## Non-goals

- ProtonMail label write-back
- ProtonMail inbox mutation
- Cross-inbox combined run orchestration
- Broad provider framework work beyond this slice

## Acceptance criteria

- One daily ProtonMail run command can fetch and classify a live bounded batch through Bridge
- The run writes a durable daily report with provider metadata
- The report captures useful label analytics even though no provider write-back occurred
- Existing weekly reporting can aggregate the new ProtonMail daily reports

## Expected tests or verification

- Test live ProtonMail daily run writes a daily report
- Test report captures suggested-label analytics while keeping write-action counts at zero
- Test weekly reporting can aggregate ProtonMail daily reports
