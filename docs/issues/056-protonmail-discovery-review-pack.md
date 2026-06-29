# ProtonMail Discovery Review Pack

Status: Current discovery artifact
Current as of: 2026-06-27
Related issue: `docs/issues/056-read-only-two-inbox-shadow-classifier-evaluation.md`
Source report: `data/classifier_eval/evaluations/classifier-corpus-eval-20260627T094106Z.json`
Post-slice report: `data/classifier_eval/evaluations/classifier-corpus-eval-20260627T102043Z.json`
Second-slice report: `data/classifier_eval/evaluations/classifier-corpus-eval-20260627T133303Z.json`

This review pack uses surfaced ProtonMail shadow misses only. It is for founder label decisions
and candidate rule design. It does not treat LLM output as ground truth, does not use provider
mutation, and should not be used to claim final unbiased performance.

## How to read this

- `Count` is the number of messages in the surfaced family.
- `Candidate label` is the proposed taxonomy mapping to approve, reject, or edit.
- Use `skip` when a family should remain unlabeled or needs a taxonomy decision rather than a rule.

## Candidate Families

| Family | Count | Candidate label | Why this likely fits | Decision |
| --- | ---: | --- | --- | --- |
| `keine-antwort@handyticket.de` / `HandyTicket Deutschland: Quittung für den Ticketkauf` | 4 | `travel`, `receipt-billing` | This is a receipt for a transit purchase: useful both as travel context and as a payment/receipt record. | implemented |
| `hello@avimedical.com` / `You have a new message` | 2 | `reply-needed` | Medical portal messages likely require attention, but may need a future `medical` taxonomy if this recurs broadly. | pending |
| `noreply@github.com` / third-party OAuth application added | 2 | `account-security` | Account access/security notice. | implemented |
| `noreply@tm.openai.com` / `[Task Update] Pure witness on a hard decision` | 2 | `spam-low-value` or `personal` | Looks like self-generated reminder/task noise; needs founder preference before downgrading. | pending |
| `noreply@zoxs.de` / status update for order | 2 | `shopping-order` | Order status update. | implemented |
| `workatastartup@ycombinator.com` / `Still looking for a job? (action required)` | 2 | `job-related` | Job-profile status/action prompt; could be low-value if no longer active. | pending |
| `accounting@caventura.com` / delivery note or shipment for order | 2 | `shopping-order` | Order/shipping record. | implemented |
| `bilety@polregio.pl` / train ticket valid on date/route | 1 | `travel` | This looks like the actual train ticket/travel document rather than merely a receipt. | implemented |
| `billing@shopify.com` / bill for Food Healthy | 1 | `receipt-billing` | Billing record. | implemented |

## Proposed First Slice

After founder approval, implement only the clearly approved families first:

1. account/security notices
2. transport tickets and transit receipts
3. shopping-order and receipt-billing records

Hold ambiguous preference families, especially self-generated OpenAI task updates and medical portal
messages, until the desired label is explicit.

## First Slice Result

Implemented on 2026-06-27 with tests in `tests/test_fixture_classifier.py`.

The ProtonMail shadow unlabeled count moved from `170 / 293` (`58.0%`) to `155 / 293`
(`52.9%`). This confirms the accepted family rules are working, but it does not change the
main conclusion: ProtonMail remains a discovery/tuning corpus with substantial uncovered
families.

Next high-leverage candidates visible after the first slice:

- Schwab eStatements: likely `financial-account`
- DHL Packstation shipment receipt: likely `shopping-order` with `receipt-billing` near miss
- Steam purchase receipts: likely `shopping-order` with `receipt-billing` near miss
- Proton subscription renewals: likely `receipt-billing` or `shopping-order` with `receipt-billing` near miss
- winSIM invoices: likely `receipt-billing`
- Avi Medical portal messages: likely `reply-needed`, but may expose a missing `medical` category
- OpenAI task updates: preference decision needed before treating as `spam-low-value`, `personal`, or leaving unlabeled

## Second Slice Result

Implemented on 2026-06-27 with tests in `tests/test_fixture_classifier.py`.

Accepted second-slice families:

- Schwab eStatement notices -> `financial-account`
- DHL Packstation drop-off receipts -> `shopping-order`
- Steam purchase receipts -> `shopping-order`
- Proton subscription renewal notices -> `receipt-billing`
- winSIM invoice notices -> `receipt-billing`

The ProtonMail shadow unlabeled count moved from `155 / 293` (`52.9%`) to `138 / 293`
(`47.1%`). Gmail reviewed metrics stayed unchanged, so this slice improved the Proton discovery
corpus without moving the Gmail benchmark.

Next candidates after the second slice:

- Avi Medical portal messages: likely `reply-needed`, but may expose a missing `medical` category
- OpenAI task updates: separate the temporary login-code family from self-generated task updates
- Y Combinator Work at a Startup re-engagement prompts: likely `job-related`
- Caventura invoice family: likely `receipt-billing`
- Polregio registration confirmations: likely `account-security`
