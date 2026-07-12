# Status

Current
Current as of: 2026-06-24
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/issues/052-prove-supervised-gmail-daily-use-on-new-mail.md`, `docs/decisions/gmail-bounded-autonomy.md`, `docs/decisions/gmail-whole-inbox-readiness-policy.md`
Blocked by: `3` counted fresh Gmail runs that satisfy the start gate defined below

# Title

Stage supervised Gmail historical rollout across the 1k+ inbox

## Type

AFK

## User-visible goal

Apply the current bounded Gmail labeling workflow across the larger historical inbox backlog in a staged, reversible, artifact-backed rollout without waiting for the full `10`-run fresh-mail proof window.

## Scope

- use the current Gmail mutation boundary only:
  - apply current `EA/` labels
  - remove `INBOX` only for `promotions` and `spam-low-value`
- start historical rollout only after the fresh-mail start gate is satisfied:
  - `3` counted fresh runs
  - all `3` evaluate to `PASS`
  - no mutation-policy violations
  - no serious false low-value handling
  - no recurring fresh-mail miss family appears in more than `1` of those `3` runs
- process the historical inbox in bounded chunks:
  - chunk `1`: `100` messages
  - chunk `2`: `200` messages
  - chunk `3`: `300` messages
  - remaining chunks: `300` to `400` messages each
- evaluate each chunk from its own run artifacts immediately after execution
- record per-chunk evidence:
  - batch ID
  - processed count
  - auto-applied count
  - inbox-removal count
  - unlabeled count
  - exception rate
  - readiness status
  - any serious misclassification observed during review
  - any recurring leftover family that appears across chunks
- permit follow-on classifier cleanup only when the same new miss family recurs in at least `2` separate chunks
- keep the rollout supervised and pauseable after every chunk

## Non-goals

- waiting for the full `10`-run fresh-mail proving window before any historical rollout begins
- broadening Gmail mutation power
- delete, trash, or broad archive behavior
- unattended scheduling
- always-on syncing
- ProtonMail write-side behavior
- broad taxonomy redesign during rollout
- cleaning up every residual miss in the same slice

## Acceptance criteria

- The rollout can begin after `3` clean counted fresh runs rather than requiring the full `10`-run proof window.
- Each historical chunk is executed and judged from its own artifacts rather than from mixed historical or latest-on-disk reports.
- The chunk ladder is explicit: `100 -> 200 -> 300 -> 300-400...`
- Expanding to the next chunk size requires the current chunk to finish without triggering a stop condition.
- The rollout summary distinguishes:
  - fresh-run start-gate evidence
  - per-chunk readiness results
  - recurring leftovers worth classifier work
  - any chunk where the rollout was paused
- The slice ends with a durable summary stating whether the larger Gmail inbox now looks safe to process under the current supervised operating model.

## Expected behavior

- Historical inbox processing starts cautiously and scales only after clean chunk results.
- The current bounded Gmail write rules remain unchanged throughout the rollout.
- A single isolated harmless leftover does not automatically stop the rollout.
- Repeated misses or any unsafe low-value handling pause expansion until understood.

## Expected tests or verification

- Before historical rollout begins:
  - confirm the `3`-run fresh-mail start gate from issue `052`
- For each historical chunk:
  - `python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size <chunk-size>`
  - `python3 scripts/check_gmail_readiness.py --account-id founder-test --batch-id <chunk-batch-id>`
- Periodically during rollout:
  - `python3 scripts/replay_gmail_readiness.py --account-id founder-test`
- Only if recurring misses appear:
  - targeted classifier tests for the specific recurring family before resuming expansion

## Run log template

- Fresh start gate:
  - run `1`: batch `<id>` | processed `<n>` | status `<PASS/WARN/PAUSE>` | notes
  - run `2`: batch `<id>` | processed `<n>` | status `<PASS/WARN/PAUSE>` | notes
  - run `3`: batch `<id>` | processed `<n>` | status `<PASS/WARN/PAUSE>` | notes
- Historical chunks:
  - chunk `1` (`100`): batch `<id>` | processed `<n>` | unlabeled `<n>` | rate `<n%>` | status `<PASS/WARN/PAUSE>` | notes
  - chunk `2` (`200`): batch `<id>` | processed `<n>` | unlabeled `<n>` | rate `<n%>` | status `<PASS/WARN/PAUSE>` | notes
  - chunk `3` (`300`): batch `<id>` | processed `<n>` | unlabeled `<n>` | rate `<n%>` | status `<PASS/WARN/PAUSE>` | notes
  - chunk `4+` (`300-400`): batch `<id>` | processed `<n>` | unlabeled `<n>` | rate `<n%>` | status `<PASS/WARN/PAUSE>` | notes

Durable log file: `docs/issues/053-stage-supervised-gmail-historical-rollout-run-log.md`

## Dependencies/order

- Start only after issue `052` has produced `3` counted fresh runs that satisfy the start gate.
- Use `docs/prd.md` as the current product source of truth.
- Treat this as the bounded follow-on rollout slice after fresh-mail proof has crossed the minimum go-ahead threshold.
- Continue the fresh-mail proof window toward `5` and `10` runs even after the historical rollout begins.

## Stop conditions requiring Founder review

- Any chunk evaluates to `PAUSE`.
- A message the founder would want kept prominent is treated as `spam-low-value` or `promotions`.
- Any mutation occurs outside the current bounded Gmail rules.
- `INBOX` removal happens without the required low-value label writeback.
- Two consecutive historical chunks breach the readiness thresholds.
- The same new miss family recurs across at least `2` chunks and appears large enough to be classifier work rather than acceptable residue.
