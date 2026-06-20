# Handoff: Issue 006 Live Gmail Read-Only Smoke

## Context

This note records the first successful live smoke test for [docs/issues/006-live-gmail-readonly-manual-fetch.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/issues/006-live-gmail-readonly-manual-fetch.md).

This follows the earlier mocked-spine checkpoint in [docs/handoff/issues-001-005-mocked-spine.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/handoff/issues-001-005-mocked-spine.md).

## What Changed

- The manual live Gmail fetch path is now runnable from the repo root without requiring `PYTHONPATH=.`
- The CLI now defaults to:
  - `data/gmail_credentials/` for OAuth client secret and token storage
  - `data/gmail_fetch/` for fetched message storage
- OAuth client secret discovery is more forgiving:
  - prefer `data/gmail_credentials/client_secret.json`
  - otherwise use exactly one `client_secret*.json` file in that directory
  - fail with a clear setup message if none or multiple candidates exist
- The local OAuth loopback flow now uses a safe loopback host and an OS-assigned free port instead of falling back to port `80`
- TLS certificate failures during token exchange or Gmail API calls now fail with an actionable setup message rather than a raw traceback
- The live OAuth path prefers Google’s official installed-app flow when the Google OAuth libraries are available, while still falling back cleanly if they are not

## Successful Smoke Test

Command run from the repo root:

```bash
python3 scripts/manual_gmail_fetch.py --account-id founder-test --batch-size 10
```

Observed terminal result:

```text
Fetched 10 new messages into founder-test-batch-1.
```

This confirms:

- local CLI invocation worked from the repo root
- local browser OAuth completed
- token exchange succeeded
- read-only Gmail API access succeeded
- bounded inbox fetch succeeded
- fetched messages were persisted into the existing review-queue shape as batch `founder-test-batch-1`

## Verification Status

Focused automated verification after the repair passes:

```bash
python3 -m unittest tests.test_live_gmail_client tests.test_live_gmail_fetch_cli -v
```

Broader Gmail-related verification:

```bash
python3 -m unittest tests.test_live_gmail_fetch_cli tests.test_live_gmail_client tests.test_gmail_fetcher tests.test_gmail_writer tests.test_gmail_retry -v
```

Result at the latest repair checkpoint: `38 tests passed`.

Manual live verification:

- One real read-only Gmail smoke test completed successfully for `founder-test`
- The CLI fetched `10` live inbox messages into `founder-test-batch-1`

## Important Constraints

- This slice is still read-only. No Gmail label writes were added or exercised here.
- Keep scope bounded to the approved Issue `006` behavior:
  - one local account
  - manual CLI trigger
  - bounded inbox fetch
  - local storage
  - review-queue insertion
- Do not add Gmail writes, background polling, multi-account UX, re-ingestion overrides, or broader provider abstraction without Founder approval.

## Remaining Risks Or Open Questions

- The smoke test proves the fetch path worked once end to end, but the fetched batch contents should still be spot-checked in local storage before treating the slice as fully accepted.
- The Google official OAuth helper libraries are preferred when present, but the local Python environment still matters for SSL/root certificate setup.
- No user-facing review UI or acceptance note exists yet for inspecting the fetched live batch beyond local stored artifacts.

## Recommended Next Step

Inspect the stored batch under `data/gmail_fetch/batches/founder-test-batch-1.json` and confirm the normalized review items look correct for a representative sample of the fetched messages.
