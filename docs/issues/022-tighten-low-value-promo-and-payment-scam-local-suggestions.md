# Title

Tighten local low-value promo and fake-payment scam suggestions

## Type

HITL

## User-visible goal

Reduce repeated review corrections by making the local classifier behave more like an executive triage assistant:

- unsolicited promotional noise should usually land in `EA/LowValue` without also surfacing `EA/Promotions`
- obvious fake payment / transaction scam mail should not look like a useful receipt or finance record

## Scope

- Update the local classifier only
- Keep the current taxonomy unchanged
- Bias generic unsolicited promotional mail toward `spam-low-value`
- Preserve a path for explicitly solicited reminders such as wishlist or requested price-drop alerts to remain promo-like rather than pure low-value
- Add a bounded safeguard so suspicious payment / transaction scam mail falls into `spam-low-value` instead of `receipt-billing` or `financial-account`
- Reuse the existing stored-batch rebuild / reclassification path for pending items only

## Non-goals

- Adding a new `dangerous` or phishing taxonomy label
- Automatic sender blocking or unsubscribe actions
- Gmail mutation changes
- Broad retraining or external-model dependence

## Acceptance criteria

- Generic unsolicited promotional emails classify to `EA/LowValue` without keeping `EA/Promotions`
- Explicitly solicited promo reminders can still remain promo-like when the message clearly looks user-requested
- Scammy payment / transaction emails such as fake `P24`-style notices classify to `EA/LowValue`
- Legitimate financial statements and real account records still classify to `EA/Finance`

## Expected tests or verification

- Test that generic promotional retail mail lands in `spam-low-value` only
- Test that solicited wishlist / price-drop reminders can still retain promo behavior
- Test that fake payment / transaction scam mail lands in `spam-low-value`
- Re-run the relevant classifier, fetcher, and live-review test suites
