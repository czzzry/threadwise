# PRD

Status: Historical context
Current as of: 2026-06-23
Superseded by: `/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/prd.md`
Related implementation slice: `docs/issues/040-prove-bounded-gmail-autonomy-end-to-end.md`

## Problem Statement

The repo already has a usable Gmail daily run that auto-applies labels and removes `INBOX` for low-value mail under bounded rules. The product risk is no longer "can it work?" but "can it be trusted not to touch the wrong emails?"

Right now the tests are stronger at the Gmail writer seam than at the end-to-end daily-run seam. That leaves a trust gap: the repo can describe the intended safety boundary, but it does not yet prove strongly enough at the highest seam that the current Gmail daily run only mutates the intended messages under the intended conditions.

If that gap stays open, the project risks drifting into endless general QA or broad new feature work before the trust boundary is explicit and well-proven.

## Solution

Harden trust around the current Gmail daily run without broadening scope.

This slice should:

- codify the current bounded Gmail autonomy policy in one current decision note
- add end-to-end proof at the daily-run seam for exact mutation targeting
- add end-to-end proof for the current `INBOX`-removal gate
- preserve the current operating model rather than inventing new actions

This is not a broad quality program. It is a bounded trust slice focused on the specific actions that can surprise or harm the user.

## User Stories

1. As the inbox owner, I want the Gmail daily run to mutate only the messages that meet the current trusted conditions, so that the assistant does not touch the wrong email.
2. As the inbox owner, I want messages outside the current trust boundary to remain untouched, so that ambiguous or risky mail stays available for manual follow-up.
3. As the inbox owner, I want `INBOX` removal to happen only after the safe preconditions are met, so that important or uncertain mail is not hidden prematurely.
4. As the inbox owner, I want ProtonMail to remain read-only during this slice, so that trust hardening does not accidentally broaden provider-side actions.
5. As the product lead, I want one current decision note that states the Gmail autonomy boundary plainly, so that future agents do not infer broader automation than the repo intends.
6. As the product lead, I want the highest-seam tests to prove exact message targeting, so that trust does not depend on reading lower-level implementation details.
7. As the product lead, I want the tests to prove which messages were auto-labeled, which were left as exceptions, and which were eligible for `INBOX` removal, so that the trust boundary is inspectable.
8. As the product lead, I want current daily report artifacts to remain consistent, so that trust hardening does not quietly break the reporting layer.
9. As the product lead, I want the slice to stop at the current action boundary, so that it does not turn into a generic eval or QA framework project.
10. As an agent working in this repo later, I want the current PRD and decision note to tell me what is actually being proven, so that I do not restart discovery or overbuild.

## Implementation Decisions

- Scope this PRD to the current Gmail daily run only. Do not broaden to general multi-provider trust work in this slice.
- Treat the current bounded Gmail actions as the behavior to prove, not the behavior to redesign.
- Keep ProtonMail read-only and out of scope for provider-side mutation.
- Write one decision note that captures:
  - which Gmail actions are currently allowed automatically
  - which conditions must be true before `INBOX` removal happens
  - which cases remain manual or exception-only
  - what evidence the workflow must record for auto-actions
- Use the highest practical seam for proof:
  - the daily-run CLI behavior and its resulting artifacts
  - the Gmail writer seam only as supporting prior art
- Add end-to-end assertions for exact message IDs that were mutated and exact message IDs that were not mutated.
- Add end-to-end assertions that `INBOX` removal only happens after successful writeback and only for the currently allowed low-value Gmail classes.
- Preserve the current daily report shape unless a tiny addition is required to expose already-existing trust evidence more clearly.
- Do not add:
  - new auto-action categories
  - new provider write actions
  - a new dashboard
  - a large eval framework
  - a new persistence model

## Testing Decisions

- Good tests for this slice prove externally visible trust behavior, not helper implementation details.
- Prefer the highest seam possible:
  - daily-run CLI behavior
  - persisted batch/report artifacts
  - Gmail client mutation calls
- Prior art already exists in:
  - `tests/test_gmail_writer.py` for bounded write and `INBOX`-removal rules
  - `tests/test_live_gmail_daily_run_cli.py` for daily-run flow and daily report writing
- This slice should strengthen the current daily-run tests so they assert:
  - exact message IDs auto-labeled
  - exact message IDs not auto-labeled
  - exact message IDs whose `INBOX` label is removed
  - exact messages left as unlabeled exceptions
- Keep tests small and scenario-based. Do not build a generalized eval harness in this slice.

## Out of Scope

- changing the core product direction
- adding new Gmail actions beyond the current bounded workflow
- changing ProtonMail to support provider-side mutation
- adding delete, trash, or broad archive behavior
- building a broad QA or eval platform
- redesigning classification policy or the label taxonomy
- large UI work on the browser review/workbench flow

## Further Notes

- The goal of this slice is to establish a stop line for trust hardening, not to create endless QA work.
- Success means the repo can prove the current Gmail daily run only auto-touches what it is supposed to touch under the current policy.
- After this slice, the project should be able to move back to product-facing work with a clearer trust foundation.
