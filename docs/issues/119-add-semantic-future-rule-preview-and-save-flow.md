# Add Semantic Future-Rule Preview and Save Flow

GitHub issue: `#45`

Parent: GitHub issue `#42`

## What to build

Let Threadwise propose and save future rules based on the actual meaning of the email and the founder's note, rather than defaulting to sender-wide rules.

The founder should be able to save a future rule without applying it to existing affected emails, and the UI should be explicit that existing emails were not changed.

## Acceptance criteria

- [x] Future-rule proposals distinguish sender + semantic pattern rules from cross-sender semantic rules.
- [x] Rule copy is plain English by default, with structured details hidden behind an expander.
- [x] A single-email rule can be shown as tentative; matched examples upgrade the confidence/impact language.
- [x] Threadwise asks at most one clarifying question when it materially improves the rule boundary.
- [x] `Teach future rule` saves future behavior without changing existing emails.
- [x] The success state says the future rule was saved and existing affected emails were not changed.
- [x] Tests cover that future-rule saving is distinct from current-email fixing and existing-email apply.

## Completion notes

Implemented in the #42 slice-2 pass:

- Future-rule previews now carry `rule_type`, `rule_type_label`, `rule_confidence`, and optional `clarifying_question`.
- Wealthsimple/account-style corrections produce sender + semantic rules instead of all-sender rules.
- Phishing/payment-style corrections can be identified as cross-sender semantic rules.
- The UI shows rule type/confidence chips and keeps structured details hidden behind an expander.
- `Teach future rule` reports that a future rule was saved and existing emails were not changed.

## Blocked by

- GitHub issue `#44`
