# Status

Historical context
Current as of: 2026-06-23
Implemented in: `tests/test_live_gmail_daily_run_cli.py` plus `docs/decisions/gmail-bounded-autonomy.md`
Superseded by: current slice selection now flows from `docs/prd.md`

# Title

Prove bounded Gmail autonomy end to end

## Type

AFK

## User-visible goal

Make the current Gmail daily run trustable enough to keep using by proving that it mutates only the intended messages and only under the current safe conditions.

## Scope

- codify the current Gmail autonomy boundary in one durable decision note
- strengthen the highest-seam Gmail daily-run tests so they assert exact mutation targeting
- prove the current `INBOX`-removal gate end to end
- preserve the current daily run, daily report, and exception-summary workflow

## Non-goals

- changing product strategy
- redesigning the taxonomy
- adding new Gmail or ProtonMail actions
- building a large eval framework
- broad UI redesign
- broad QA beyond the current Gmail trust boundary

## Acceptance criteria

- A current decision note defines the Gmail bounded-autonomy policy clearly enough to guide implementation and review.
- Daily-run tests assert exact message IDs that receive label writeback and exact message IDs that do not.
- Daily-run tests assert exact message IDs that have `INBOX` removed and prove the current safe gating conditions.
- Current daily report behavior remains intact and continues to describe auto-applied counts, inbox removals, classified messages, and unlabeled exceptions.
- No new provider-side actions or broader automation scope are introduced.

## Expected behavior

- The Gmail daily run continues to auto-apply labels for trusted messages.
- Unlabeled or otherwise out-of-boundary messages remain untouched and visible for manual follow-up.
- `INBOX` removal continues to happen only for the currently allowed Gmail low-value classes and only after the current writeback gate is satisfied.
- ProtonMail remains read-only.

## Expected tests or verification

- Extend the daily-run CLI tests to prove exact mutation targeting at the highest seam.
- Reuse the current Gmail writer tests as prior art for safe writeback and inbox-removal behavior.
- Re-run the daily-run, Gmail writer, and weekly report suites to ensure trust hardening does not break the reporting path.

## Dependencies/order

- Builds on the current operating model and can start immediately.
- Use `docs/prd.md` and `docs/decisions/gmail-bounded-autonomy.md` as the current source of truth for this slice.

## Stop conditions requiring Founder review

- The work starts changing the auto-apply policy instead of proving the current one.
- The work broadens ProtonMail beyond read-only.
- The work requires new private-email exposure beyond the current local artifact model.
- The slice starts expanding into general QA or eval infrastructure rather than bounded trust proof.
