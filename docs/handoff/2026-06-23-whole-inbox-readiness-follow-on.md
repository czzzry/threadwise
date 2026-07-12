# Handoff

Current as of: 2026-06-24

## Current source of truth

Read in this order before continuing:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md`
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. Current issue briefs under `docs/issues/`

## What changed

- Issue 040 trust gap is now proven by tests:
  - daily-run tests assert exact Gmail mutation targets
  - inbox removal is gated on successful label writeback
- Added recurring reviewed-unlabeled inspection:
  - `src/unlabeled_exception_report.py`
  - `src/unlabeled_exception_report_cli.py`
  - `scripts/inspect_unlabeled_exception_clusters.py`
- Implemented focused classifier cleanup slices:
  - issue 042: LinkedIn `jobs-noreply` recommendations -> `job-related`
  - issue 043: Trainline delay and trip-readiness mail -> `travel`
  - issue 044: Amazon `Shipped:` updates -> `shopping-order`
  - issue 045: Duolingo password exposure and Google linked-services reminders -> `account-security`
  - issue 046: `Young, Jenny <clinic.contact@example.test>` institutional memos -> `spam-low-value`
  - issue 047: `Concilia <no-reply@conciliainc.com>` MGM settlement notice -> `spam-low-value`
  - issue 048: final singleton cleanup:
    - LinkedIn report acknowledgement -> `spam-low-value`
    - iNaturalist engagement nudge -> `spam-low-value`
    - xAI API product announcement -> `spam-low-value`
    - Coursera / University of Michigan course promo -> `spam-low-value`
    - Prime Video subscription-ended notice -> `shopping-order`
    - Przelewy24 transaction notice -> `spam-low-value`
- issue 049: explicit Gmail whole-inbox readiness policy written in `docs/decisions/gmail-whole-inbox-readiness-policy.md`
- issue 050: local Gmail readiness-check command implemented:
  - `src/gmail_readiness_check_cli.py`
  - `scripts/check_gmail_readiness.py`
- issue 051: local Gmail stored-batch readiness replay implemented:
  - `src/gmail_readiness_replay.py`
  - `src/gmail_readiness_replay_cli.py`
  - `scripts/replay_gmail_readiness.py`
- follow-on classifier cleanup from stored replay warning in batch `20`:
  - `upGrad KnowledgeHut <mailer@certs.knowledgehut.com>` event promos -> `spam-low-value`
  - `Amazon Alexa <account-update@amazon.com>` Alexa+ upgrade notice -> `spam-low-value`
  - `Amazon Prime <prime@amazon.com>` membership-resume notice -> `shopping-order`
  - `YouTube <noreply-purchases@youtube.com>` Premium Lite welcome / recurring-charge notice -> `shopping-order`
- follow-on classifier cleanup from the first new real live batch (`22`):
  - `Instaffo <notifications@app.instaffo.com>` registration / job-platform re-engagement mail -> `job-related`
  - `Google Home <googlehome@google.com>` Gemini for Home rollout notices -> `spam-low-value`
- fixed a real live Gmail fetch gap in `src/live_gmail_client.py`:
  - `messages.list` now paginates past Gmail's first `500` results instead of silently treating the first page as the whole inbox
  - coverage added in `tests/test_live_gmail_client.py`
- confirmed the live founder Gmail inbox had substantial historical backlog before the pagination fix:
  - `3084` messages currently in `INBOX`
  - `503` already present in stored batch state while still in `INBOX`
  - `2581` additional `INBOX` messages not yet represented in local batch storage at that point
- historical Gmail backfill moved materially forward after the pagination fix:
  - `founder-test-batch-23`: `800` fetched, mutation evidence verified, replay warning reduced from `75` unlabeled to `2`
  - `founder-test-batch-24`: `100` fetched, `92` auto-applied writes, `58` inbox removals, `8` run-time unlabeled
  - `founder-test-batch-25`: `100` fetched, `95` auto-applied writes, `45` inbox removals, `5` run-time unlabeled
  - `founder-test-batch-26`: `10` fetched, `9` auto-applied writes, `5` inbox removals, `1` run-time unlabeled
  - `founder-test-batch-27`: `10` fetched, `10` auto-applied writes, `2` inbox removals, `0` run-time unlabeled
  - `founder-test-batch-28`: `10` fetched, `10` auto-applied writes, `5` inbox removals, `0` run-time unlabeled
  - `founder-test-batch-29`: `10` fetched, `8` auto-applied writes, `3` inbox removals, `2` run-time unlabeled, both later closed under replay
- added narrow classifier coverage for the historical backfill families discovered in batches `23`-`29`, including:
  - Prime Video channel booking / cancellation / special-offer lifecycle mail -> `shopping-order`
  - Amazon subscription billing risk, Audible membership-state mail, LinkedIn Premium cancellation, YouTube Premium welcome -> `shopping-order`
  - PayPal contact-change variant, TD phishing advisory -> `account-security` / `financial-account`
  - Wise / Wealthsimple / Sun Life / Kasa Stefczyka finance notices -> `financial-account`
  - Reserve with Google reservations -> `calendar-event`
  - PID Litacka registration -> `travel`
  - iNaturalist engagement nudges, PMI event promos, OpenAI / GOG / LinkedIn policy-feed style updates, Purple wifi promo, Sporcle trophy mail -> `spam-low-value`
  - German shipment/order updates such as Mein Lieblingsrahmen `versendet` mail -> `shopping-order`
- Marked issues 041-045 as implemented.

## Validation

- `python3 -m unittest tests.test_live_gmail_daily_run_cli tests.test_gmail_writer tests.test_weekly_inbox_report_cli`
- `python3 -m unittest tests.test_unlabeled_exception_report_cli tests.test_local_batch_index_cli tests.test_local_batch_status_cli tests.test_fixture_classifier`
- Both command groups passed on 2026-06-23.
- `python3 -m unittest tests.test_fixture_classifier`
- Current-gap reclassification check over reviewed unlabeled Gmail items now reports `remaining_count 0`.
- `python3 -m unittest tests.test_gmail_readiness_check_cli tests.test_live_gmail_daily_run_cli tests.test_weekly_inbox_report_cli tests.test_local_batch_status_cli`
- The readiness-check suite and related Gmail artifact/report suites passed on 2026-06-23.
- `python3 -m unittest tests.test_gmail_readiness_replay_cli`
- The stored-batch readiness replay suite passed on 2026-06-23.
- `python3 scripts/replay_gmail_readiness.py --account-id founder-test`
- `python3 -m unittest tests.test_fixture_classifier tests.test_gmail_readiness_replay_cli`
- The batch-20 replay cleanup tests passed on 2026-06-23.
- `python3 -m unittest tests.test_gmail_readiness_replay_cli tests.test_gmail_readiness_check_cli tests.test_live_gmail_daily_run_cli tests.test_weekly_inbox_report_cli tests.test_local_batch_status_cli tests.test_unlabeled_exception_report_cli tests.test_fixture_classifier`
- The broader Gmail readiness and classifier suite passed on 2026-06-23 after the live-batch follow-on cleanup.
- Stored replay over founder-test Gmail batches now reports:
  - overall status `PASS`
  - `22` stored batches
  - `770` stored messages
  - `22` replay-pass batches
  - `0` replay-warn batches
  - `0` replay-pause batches
  - `0` remaining frontier unlabeled messages under the current classifier
  - `6` batches with verified mutation evidence
  - `0` stored mutation-policy violations
- `python3 scripts/daily_live_gmail_run.py --account-id founder-test`
- New real Gmail run result on 2026-06-23:
  - batch `founder-test-batch-22`
  - `22` fetched messages
  - `19` auto-applied writes
  - `12` inbox removals
  - `3` unlabeled exceptions at run time
- `python3 scripts/daily_live_gmail_run.py --account-id founder-test`
- Immediate follow-on run after classifier cleanup reported `No new messages found.`
- `python3 -m unittest tests.test_fixture_classifier tests.test_live_gmail_client tests.test_live_gmail_daily_run_cli tests.test_gmail_readiness_replay_cli tests.test_gmail_readiness_check_cli tests.test_weekly_inbox_report_cli tests.test_local_batch_status_cli tests.test_unlabeled_exception_report_cli`
- Broader Gmail replay / daily-run / classifier suite passed on 2026-06-24 with `125` tests.
- `python3 scripts/replay_gmail_readiness.py --account-id founder-test`
- Current stored founder Gmail replay now reports:
  - overall status `PASS`
  - `29` stored batches
  - `1810` stored messages
  - `29` replay-pass batches
  - `0` replay-warn batches
  - `0` replay-pause batches
  - `0` remaining frontier unlabeled messages under the current classifier
  - `13` batches with verified mutation evidence
  - `0` stored mutation-policy violations
- `python3 -m unittest tests.test_live_gmail_client tests.test_fixture_classifier tests.test_live_gmail_daily_run_cli tests.test_gmail_readiness_replay_cli tests.test_gmail_readiness_check_cli tests.test_weekly_inbox_report_cli tests.test_local_batch_status_cli tests.test_unlabeled_exception_report_cli`
- Broader Gmail replay / daily-run / classifier suite passed on 2026-06-24 after live transport hardening and larger historical backfill cleanup with `133` tests.
- `python3 scripts/replay_gmail_readiness.py --account-id founder-test`
- Current stored founder Gmail replay now reports:
  - overall status `PASS`
  - `33` stored batches
  - `2140` stored messages
  - `33` replay-pass batches
  - `0` replay-warn batches
  - `0` replay-pause batches
  - `0` remaining frontier unlabeled messages under the current classifier
  - `17` batches with verified mutation evidence
  - `0` stored mutation-policy violations
- live Gmail transport is now hardened in `src/live_gmail_client.py` with bounded request timeouts and retries for transient timeout / `5xx` failures, and the behavior is covered in `tests/test_live_gmail_client.py`
- larger live historical backfill batches now complete:
  - `founder-test-batch-30`: `30` fetched, `30` auto-applied writes, `10` inbox removals, `0` run-time unlabeled
  - `founder-test-batch-31`: `100` fetched, `87` auto-applied writes, `38` inbox removals, `13` run-time unlabeled, later closed under replay
  - `founder-test-batch-32`: `100` fetched, `93` auto-applied writes, `52` inbox removals, `7` run-time unlabeled, later closed under replay
  - `founder-test-batch-33`: `100` fetched, `89` auto-applied writes, `46` inbox removals, `11` run-time unlabeled, later closed under replay

## Measured whole-inbox gap

Using stored Gmail batches for `founder-test` and re-running the current classifier against previously reviewed unlabeled items:

- before follow-on cleanup in this session: `still_unlabeled = 16`
- after LinkedIn slice: `still_unlabeled = 15`
- after Trainline slice: `still_unlabeled = 13`
- after Amazon + account-reminder slices: `still_unlabeled = 10`
- after `Young/Jenny` and `Concilia` low-value slices plus final singleton cleanup: `still_unlabeled = 0`

Recurring reviewed-unlabeled total from stored history is still `155`, but most of that history is now stale relative to the current classifier and the current replay frontier remains `0`.

## Remaining unlabeled frontier

The previously identified frontier has now been explicitly resolved under the current classifier. Re-running the current classifier against historically reviewed unlabeled Gmail items leaves `0` remaining unlabeled messages in the current measured frontier.

## Current stored replay result

The new stored-batch replay command now shows a stronger answer than the earlier single-run readiness check alone:

- the current classifier now closes the historical reviewed-unlabeled frontier to `0`,
- replaying the current classifier across the stored founder-test Gmail corpus now yields no `WARN` or `PAUSE` batches across `33` batches,
- the previous stored replay warnings in the historical backfill are now reduced to zero under the current classifier,
- new real live validation batches (`26`-`33`) now replay cleanly with verified mutation evidence,
- the current stored replay status is now `PASS`,
- stored mutation evidence remains partial because only `17` of `33` Gmail batches currently have full write and inbox-removal status artifacts.

## Recommended next bounded step

The measured Gmail reviewed-unlabeled frontier is now closed and the readiness policy is now explicit, so the next bounded step should no longer be taxonomy cleanup or policy writing. The next sensible slice is operational hardening around the live backfill path:

1. continue historical backfill in `100`-message chunks while the hardened live client remains stable, because this now works and materially reduces the one-time backlog,
2. persist or summarize run-time exception families for large backfill batches so new misses can be reviewed without manually replaying every time,
3. clarify incremental-fetch / repeat-run reliability expectations for day-over-day use once the one-time backlog is reduced further.
