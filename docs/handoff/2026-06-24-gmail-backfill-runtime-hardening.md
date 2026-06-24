# Handoff

Current as of: 2026-06-24

## Current source of truth

Read in this order before continuing:

1. `/Users/cezarybaraniecki/Documents/AI project/email-agent/AGENTS.md`
2. `/Users/cezarybaraniecki/Documents/AI project/email-agent/CONTEXT.md`
3. `/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/v2-alignment.md`
4. `/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/prd.md`
5. `/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/checkpoints/current-operating-model-2026-06-22.md`
6. `/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/handoff/2026-06-23-whole-inbox-readiness-follow-on.md`
7. this handoff

## What changed in this session

- Fixed the real live Gmail historical-fetch bug in `src/live_gmail_client.py`:
  - Gmail `messages.list` now paginates beyond the first `500` messages.
- Hardened live Gmail transport in `src/live_gmail_client.py`:
  - bounded HTTP timeout
  - transient retry handling for timeout / retryable `5xx` / `429` style failures
  - tests added in `tests/test_live_gmail_client.py`
- Continued founder Gmail historical backfill with live batches:
  - `founder-test-batch-30`: `30` fetched, `30` classified, `0` unlabeled
  - `founder-test-batch-31`: `100` fetched, `87` classified, `13` run-time unlabeled, later closed under replay
  - `founder-test-batch-32`: `100` fetched, `93` classified, `7` run-time unlabeled, later closed under replay
  - `founder-test-batch-33`: `100` fetched, `89` classified, `11` run-time unlabeled, later closed under replay
- Added narrow classifier coverage in `src/fixture_classifier.py` plus tests in `tests/test_fixture_classifier.py` for families discovered in the larger live backfill:
  - PayPal payment receipts -> `receipt-billing`
  - merchant order / paid / shipped notices such as Mein Lieblingsrahmen -> `shopping-order`
  - Talkpal subscription activation -> `shopping-order`
  - Ubisoft / LinkedIn / Google / Cloud4wi verification or security mail -> `account-security`
  - TD disruption reminders -> `financial-account`
  - eBay member questions -> `reply-needed` + `shopping-order`
  - eBay review / recently-viewed follow-ups -> `spam-low-value`
  - eBay / FedEx / Hermes shipment updates -> `shopping-order`
  - Sun Life cybersecurity promo and iNaturalist live-event invites -> `spam-low-value`
- Continued founder Gmail historical backfill further with live batches:
  - `founder-test-batch-34`: `100` fetched, `94` auto-applied writes, `35` inbox removals, `6` run-time unlabeled, later closed under replay
  - `founder-test-batch-35`: `100` fetched, `89` auto-applied writes, `31` inbox removals, `11` run-time unlabeled, later closed under replay
  - `founder-test-batch-36`: `100` fetched, `63` auto-applied writes, `20` inbox removals, `37` run-time unlabeled, reduced to `3` remaining unlabeled under replay
- Added narrow classifier coverage for the new live backfill families from batches `34`-`36`, including:
  - IMF data-portal shutdown, Voi and Ticketmaster policy mail, Pantak recruiting spam, AbeBooks welcome -> `spam-low-value`
  - Slack, eBay new-device, Battle.net verification / password-change, Google Photos storage cutoff, Trello dormant-account prompts -> `account-security`
  - FedEx customs clearance, Royal Mail, DHL branch / return / in-transit, GLS parcel notices, Berliner Büchertisch / medimops / AbeBooks order mail, YouTube channel memberships, Amazon payment-declined notices -> `shopping-order`
  - Interac request / expired request notices -> `financial-account`
  - active PayPal payment receipts -> `receipt-billing`

## Current measured state

- `python3 scripts/replay_gmail_readiness.py --account-id founder-test`
- Current result:
  - overall status `PASS`
  - `36` stored batches
  - `2440` stored messages
  - `36` replay-pass batches
  - `0` replay-warn batches
  - `0` replay-pause batches
  - `0` frontier remaining unlabeled
  - `20` batches with verified mutation evidence
  - `0` mutation-policy violations
  - `founder-test-batch-36` now replays at `PASS` with `3` unlabeled (`3.00%`) instead of the original `37` run-time misses

## Validation

- `python3 -m unittest tests.test_live_gmail_client tests.test_fixture_classifier tests.test_live_gmail_daily_run_cli tests.test_gmail_readiness_replay_cli tests.test_gmail_readiness_check_cli tests.test_weekly_inbox_report_cli tests.test_local_batch_status_cli tests.test_unlabeled_exception_report_cli`
- Passed with `139` tests on 2026-06-24 after the batch `34`-`36` classifier follow-up.

## Important operational conclusion

The one-time huge-inbox cleanup path is now materially more viable:

- larger live backfill runs no longer hang indefinitely at the Gmail transport layer
- `100`-message live backfill batches now complete
- the current classifier has been keeping up with the new families those larger batches reveal

This does **not** mean the inbox is fully backfilled yet. It means the repo can now continue the one-time historical catch-up in practical `100`-message chunks instead of tiny `10`-message chunks.

## Next bounded step

The first current product ambiguity is now isolated:

1. `founder-test-batch-36` still has `3` remaining unlabeled messages, all from `Hannah Klein <hannah.klein@ue-germany.com>` with subject `Your enquiry with University of Europe for Applied Sciences`.
2. Those mails are repeated study-admissions / advisor follow-ups that may merit response, but the current taxonomy has no clean `education` / `admissions` label and forcing them into `job-related` would be semantically wrong.
3. Resolve that taxonomy/product decision before continuing further classifier cleanup for this family.
4. After that decision, resume live Gmail historical backfill in `100`-message chunks.

## Exact next commands

1. Decide how University of Europe admissions / advisor follow-up mail should map in the current taxonomy:
   - new label family,
   - `personal`,
   - `reply-needed` with a different companion label,
   - or deliberate `spam-low-value`.
2. After that decision:
   - add narrow tests first in `tests/test_fixture_classifier.py`
   - implement the corresponding rule in `src/fixture_classifier.py`
   - rerun:
     - `python3 -m unittest tests.test_live_gmail_client tests.test_fixture_classifier tests.test_live_gmail_daily_run_cli tests.test_gmail_readiness_replay_cli tests.test_gmail_readiness_check_cli tests.test_weekly_inbox_report_cli tests.test_local_batch_status_cli tests.test_unlabeled_exception_report_cli`
     - `python3 scripts/replay_gmail_readiness.py --account-id founder-test`
3. Then resume:
   - `python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 100`

## User preference

- The founder wants minimal interruption.
- Do as much as possible without asking for input.
- Live Gmail access and bounded real Gmail mutations for this workflow have already been explicitly approved in this conversation.
