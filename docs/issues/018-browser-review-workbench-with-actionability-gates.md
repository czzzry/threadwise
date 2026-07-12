# Title

Browser review workbench with actionability capture and automation gate summaries

## Type

AFK

## User-visible goal

Let the founder use the browser review UI as the main local review workbench across stored batches, capture a small explicit inbox-actionability signal during manual review, and receive local threshold reminders plus a computed low-value automation gate summary before enabling any new auto-apply behavior.

## Scope

- Extend the existing local browser review UI from one stored batch into a small stored-batch workbench
- Let the founder see and open stored batches from the browser review surface without Gmail API calls
- Keep browser review decisions persisted in the same stored review contract already used by the current CLI/browser review flow
- Add a minimal actionability review signal for plausible inbox-removal candidates only:
  - `safe-to-remove-from-inbox`
  - `keep-in-inbox`
- Keep retrieval labels and inbox policy as separate concepts
- Allow actionability to disagree with retrieval labels when appropriate
- Default plausible inbox-removal candidates to a visible `safe-to-remove-from-inbox` suggestion that the reviewer can override quickly
- Limit initial plausible inbox-removal candidates to messages suggested or reviewed as:
  - `promotions`
  - `spam-low-value`
  - `newsletter`
  - obvious routine `shopping-order`
  - obvious routine `receipt-billing`
- Surface local reminders when cumulative reviewed-message counts cross:
  - `50` reviewed messages: informational checkpoint
  - `100` reviewed messages: first automation decision gate
  - `200` reviewed messages: stronger confidence checkpoint
- Compute a local automation-gate summary over reviewed outcomes, but keep the founder as the final approver for any future automation enablement
- Keep this slice fully local and read/write only against existing local stored batch artifacts
- Define expected behavior and tests before implementation begins

## Non-goals

- Gmail fetch from the browser UI
- Gmail label write-back from the browser UI
- automatic enabling of inbox-removal automation
- deleting, trashing, or permanently removing messages
- expanding the fixed retrieval taxonomy in this slice
- fully general policy engines or background automation
- cross-account dashboarding
- exposing private email content beyond what the current review task already requires

## Acceptance criteria

- A user can open the browser review surface and navigate among stored batches without leaving the local UI
- The browser workbench makes it easy to find the next pending stored batch to review
- Browser review still saves the same bounded local review decisions as the current stored-batch review flow
- Plausible inbox-removal candidates expose an explicit actionability choice during review
- Actionability is captured separately from retrieval labels and may disagree with them
- Actionability defaults are visible and easy to override
- The workbench surfaces local reminders at `50`, `100`, and `200` cumulative reviewed messages
- At `100` reviewed messages, the system can compute a local low-value automation gate summary based only on messages where actionability was explicitly reviewed
- The computed gate summary does not itself enable automation; it prepares the founder to make that decision
- The public flow performs no Gmail API calls, no Gmail writes, no inbox-removal mutations, and no delete/trash behavior

## Expected behavior

- The user starts the local browser review UI and lands on a small workbench view that can show available stored batches plus their high-level status
- The user can open one stored batch from that workbench and continue using the browser as the main review surface
- The UI continues to show the existing review controls for retrieval labels
- For plausible inbox-removal candidates only, the UI also shows a small actionability control with:
  - `safe to remove from inbox`
  - `keep in inbox`
- The UI uses a visible default of `safe to remove from inbox` for those candidates, but the reviewer can override before saving
- Actionability is not required on messages that are not plausible inbox-removal candidates
- The system stores enough local actionability data with reviewed outcomes to support future gate evaluation without inventing a separate parallel review store
- The workbench computes cumulative reviewed-message thresholds across stored batches and surfaces reminders when the founder crosses `50`, `100`, or `200`
- The `100`-message gate summary is local-only and uses only reviewed messages where actionability was explicitly captured
- The first gate summary is framed for the founder's low-value automation policy only, with the intended first automation boundary being:
  - low-value labels only
  - remove `INBOX` only
  - new messages only after future founder approval
- The gate summary should help the founder answer whether `promotions` plus `spam-low-value` are precise enough for the first bounded automation step
- The slice does not fetch new batches, apply Gmail labels, remove `INBOX`, or enable automation from the browser UI

## Expected tests or verification

- Test that the browser workbench can discover and render multiple stored batches without Gmail calls
- Test that a user can open a pending stored batch from the workbench and still save review decisions in the existing persisted shape
- Test that plausible inbox-removal candidates expose actionability controls while non-candidates do not
- Test that actionability values persist locally and reload correctly when the batch is reopened
- Test that actionability can disagree with retrieval labels without breaking the stored review contract
- Test that the visible default actionability for plausible candidates is `safe to remove from inbox`
- Test that cumulative reminder thresholds at `50`, `100`, and `200` are surfaced correctly from stored reviewed outcomes
- Test that the `100`-message gate summary includes only messages with explicit actionability review
- Test that the public browser workbench flow performs no Gmail API calls, no Gmail writes, and no inbox-removal mutations
- Manual verification on existing stored founder batches after issue approval

## Dependencies/order

- Follows issue `017` as the next browser-review-centered vertical slice
- Reuses the existing stored batch review contract and local batch summaries rather than inventing a second review model
- Should be approved before implementation as one bounded review-workbench slice
- Future Gmail fetch/apply UI work, if needed, should be handled in a separate issue after this slice proves its value

## Stop conditions requiring Founder review

- The slice starts broadening into live Gmail fetch, live Gmail label write-back, or live inbox-removal mutation from the browser UI
- The slice appears to require taxonomy expansion rather than capturing a bounded actionability signal
- The slice pressures the project toward a broad dashboard or policy engine instead of a review workbench
- The actionability concept cannot be integrated into the existing stored review contract cleanly enough to stay bounded
- The slice appears to require default exposure of private email content beyond what the current review task already shows
