# Add Semantic Future-Rule Preview and Save Flow

GitHub issue: `#45`

Parent: GitHub issue `#42`

## What to build

Let Threadwise propose and save future rules based on the actual meaning of the email and the founder's note, rather than defaulting to sender-wide rules.

The founder should be able to save a future rule without applying it to existing affected emails, and the UI should be explicit that existing emails were not changed.

## Acceptance criteria

- [ ] Future-rule proposals distinguish sender + semantic pattern rules from cross-sender semantic rules.
- [ ] Rule copy is plain English by default, with structured details hidden behind an expander.
- [ ] A single-email rule can be shown as tentative; matched examples upgrade the confidence/impact language.
- [ ] Threadwise asks at most one clarifying question when it materially improves the rule boundary.
- [ ] `Teach future rule` saves future behavior without changing existing emails.
- [ ] The success state says the future rule was saved and existing affected emails were not changed.
- [ ] Tests cover that future-rule saving is distinct from current-email fixing and existing-email apply.

## Blocked by

- GitHub issue `#44`
