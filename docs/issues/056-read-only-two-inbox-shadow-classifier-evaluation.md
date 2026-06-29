# Status

Current
Current as of: 2026-06-27
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/v2-alignment.md`, `docs/decisions/gmail-bounded-autonomy.md`, `docs/issues/052-prove-supervised-gmail-daily-use-on-new-mail.md`, `docs/issues/053-stage-supervised-gmail-historical-rollout.md`

# Title

Read-only two-inbox shadow classifier evaluation

## Type

AFK

## User-visible goal

Use the stored Gmail corpus and a read-only ProtonMail corpus to improve confidence in the classifier faster than waiting for low-volume fresh Gmail days, while keeping evaluation scientifically honest and avoiding provider-side mutation.

## Scientific setup

Use three evidence buckets with different trust levels.

1. Gmail reviewed benchmark
   - Source: stored Gmail batches with human-reviewed `final_labels`.
   - Use for: regression checks, label-distribution sanity, finding places where the current classifier no longer matches reviewed decisions.
   - Do not use as: a clean unseen test set. Many Gmail rules were created from this history, so it is training-adjacent evidence.

2. Gmail post-freeze fresh evidence
   - Source: issue `052` counted fresh Gmail runs after the current classifier freeze.
   - Use for: highest-quality ongoing proof of supervised daily Gmail behavior.
   - Do not use as: a fast high-volume benchmark, because volume is low and calendar-dependent.

3. ProtonMail shadow corpus
   - Source: read-only ProtonMail batches fetched/imported into local artifacts.
   - Use for: out-of-distribution shadow evaluation, recurring miss discovery, and candidate classifier improvements.
   - Do not use as: ground truth until the founder reviews selected examples or accepts suggested labels.

## Scope

- keep ProtonMail read-only
- do not perform Gmail or ProtonMail provider-side mutation
- produce local artifacts only
- report separate evidence for Gmail and ProtonMail rather than mixing providers into one score
- distinguish reviewed ground truth from unreviewed shadow suggestions
- optionally use an LLM only as a hypothesis generator over explicitly approved fields
- turn accepted improvements into narrow tested classifier slices

## Non-goals

- unattended scheduling
- background syncing
- provider-side ProtonMail writes
- treating LLM output as ground truth
- broad taxonomy redesign before concrete miss families are visible
- sending private email content to an external model without explicit approval

## Acceptance criteria

- A local read-only evaluation run can summarize:
  - reviewed Gmail benchmark size and current-classifier agreement
  - unreviewed ProtonMail shadow size
  - current classifier label distribution by provider
  - unlabeled counts and rates by provider
  - top recurring unlabeled or low-confidence sender/subject families
- The report clearly marks which sections have human-reviewed labels and which are shadow-only.
- Any LLM-generated suggestions are saved as candidates, not applied as rules automatically.
- Follow-on classifier work is opened only for recurring, reviewable families or founder-approved examples.

## Initial baseline

Measured on 2026-06-27 after the Amazon passkey fix and ProtonMail RFC 2047 header decoding:

- Gmail stored corpus:
  - total messages: `3383`
  - human-reviewed benchmark messages: `3001`
  - shadow/unreviewed messages: `382`
  - current-classifier unlabeled: `34` (`1.0%`)
  - reviewed exact-match: `2591 / 3001` (`86.3%`)
  - reviewed overlap: `2790 / 3001` (`93.0%`)
- ProtonMail read-only shadow corpus:
  - fetched messages: `293`
  - provider-side mutations: `0`
  - human-reviewed benchmark messages: `0`
  - shadow/unreviewed messages: `293`
  - current-classifier unlabeled: `170` (`58.0%`)
  - top recurring unlabeled families include Schwab eStatements, HandyTicket receipts, DHL shipping receipts, Steam purchase receipts, Proton subscription renewals, winSIM invoices, GitHub OAuth/application security notices, and OpenAI task updates.

### Frozen ProtonMail family split

The ProtonMail corpus is split by deterministic sender/normalized-subject family, not by
individual message, so repeated families do not leak across tuning and holdout buckets.

Important caveat: the first read-only ProtonMail daily run printed the full unlabeled exception
list before the split existed. That means the ProtonMail corpus is still valuable as a discovery
and tuning corpus, but it should not be overclaimed as a pristine final exam for unlabeled-miss
generalization. Use future fresh mail or a separate corpus such as Hotmail for the cleanest final
generalization check if that level of proof is needed.

- Discovery:
  - total messages: `151`
  - unlabeled: `84` (`55.6%`)
  - use for: founder review, LLM-assisted clustering if explicitly approved, and candidate rule/memory design
- Validation:
  - total messages: `74`
  - unlabeled: `41` (`55.4%`)
  - use for: post-tuning checks after discovery-driven changes
- Holdout:
  - total messages: `68`
  - unlabeled: `45` (`66.2%`)
  - use for: internal post-tuning check only; not a pristine final exam because the unlabeled
    exception list was already surfaced

Do not tune directly from validation or holdout examples. If a holdout family is inspected
for product reasons, mark the holdout as contaminated and regenerate or replace it before
claiming final generalization evidence.

Current local report with split manifest:

`data/classifier_eval/evaluations/classifier-corpus-eval-20260627T094106Z.json`

## First discovery slice result

Implemented on 2026-06-27 after founder review of the first ProtonMail discovery pack.

Accepted rule families:

- Amazon Canada passkey notice -> `account-security`
- GitHub third-party OAuth application notice -> `account-security`
- HandyTicket transit purchase receipt -> `travel`, `receipt-billing`
- Polregio train ticket document -> `travel`
- ZOXS order status update -> `shopping-order`
- Caventura shipment and delivery-note order documents -> `shopping-order`
- Shopify bill notice -> `receipt-billing`

Post-slice local corpus report:

`data/classifier_eval/evaluations/classifier-corpus-eval-20260627T102043Z.json`

Results:

- Gmail stored corpus:
  - total messages: `3383`
  - current-classifier unlabeled: `34` (`1.0%`)
  - reviewed exact-match: unchanged at `2591 / 3001` (`86.3%`)
- ProtonMail read-only shadow corpus:
  - total messages: `293`
  - current-classifier unlabeled: `155` (`52.9%`)
  - discovery split: `67 / 150` unlabeled (`44.7%`)
  - validation split: `39 / 65` unlabeled (`60.0%`)
  - holdout split: `49 / 78` unlabeled (`62.8%`)

Gmail rollout guardrails after this slice:

- Latest fresh Gmail readiness: `PASS` on `founder-test-batch-50`
- Stored Gmail readiness replay: `PASS` across `50` batches / `3373` messages
- Replay warn batches: `0`
- Replay pause batches: `0`
- Mutation evidence violations: `0`

Interpretation: the approved ProtonMail slice reduced known shadow misses, but the remaining
ProtonMail unlabeled rate is still high enough that ProtonMail should continue to be treated as
a discovery/tuning corpus rather than evidence that the current deterministic classifier is
generally complete.

## Second discovery slice result

Implemented on 2026-06-27 after the first ProtonMail discovery families landed cleanly.

Accepted second-slice families:

- Schwab eStatement notices -> `financial-account`
- DHL Packstation drop-off receipts -> `shopping-order`
- Steam purchase receipts -> `shopping-order`
- Proton subscription renewals -> `receipt-billing`
- winSIM invoices -> `receipt-billing`

Post-slice local corpus report:

`data/classifier_eval/evaluations/classifier-corpus-eval-20260627T133303Z.json`

Results:

- Gmail stored corpus:
  - total messages: `3383`
  - current-classifier unlabeled: `34` (`1.0%`)
  - reviewed exact-match: unchanged at `2591 / 3001` (`86.3%`)
- ProtonMail read-only shadow corpus:
  - total messages: `293`
  - current-classifier unlabeled: `138` (`47.1%`)
  - discovery split: `63 / 150` unlabeled (`42.0%`)
  - validation split: `32 / 65` unlabeled (`49.2%`)
  - holdout split: `43 / 78` unlabeled (`55.1%`)

Interpretation: the second slice removed another recurring block of clearly reviewable ProtonMail
misses without moving the Gmail benchmark. ProtonMail is still a discovery corpus, but the
remaining miss set is now concentrated more heavily in preference-sensitive, taxonomy-sensitive,
or account-verification families rather than obvious billing/order statements.

## Expected process

1. Freeze the current classifier state after the Amazon passkey fix and stored replay PASS.
2. Run a local Gmail reviewed benchmark report from stored artifacts.
3. With explicit approval, fetch/import ProtonMail read-only batches.
4. Run a ProtonMail shadow report from stored artifacts.
5. If approved, ask an LLM to cluster only the selected shadow exceptions/candidates.
6. Review the highest-leverage candidates with the founder.
7. Implement only narrow tested rules for accepted improvements.

## Stop conditions requiring founder review

- Any proposal would broaden Gmail mutation, ProtonMail mutation, delete, trash, archive, send, or reply behavior.
- The work starts treating LLM suggestions as labels without review.
- The evaluation requires sending full private email bodies externally without explicit approval.
- The evidence suggests the current taxonomy is missing a recurring category rather than merely a sender-pattern rule.
