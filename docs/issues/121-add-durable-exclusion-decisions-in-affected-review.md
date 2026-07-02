# Add Durable Exclusion Decisions in Affected Review

GitHub issue: `#47`

Parent: GitHub issue `#42`

## What to build

Let the founder exclude emails from an affected-rule review and save durable exceptions so the same rule does not hit excluded emails later.

Exclusion should be quick and not require an explanation, but Threadwise may optionally ask why or suggest a generalized exception if it can infer a useful boundary.

## Acceptance criteria

- [ ] Each affected row can be excluded from the pending rule apply set.
- [ ] Excluding an email immediately saves an exact durable exception for that rule/email.
- [ ] The UI confirms: `Exception saved. This rule will not apply to this email/pattern later.`
- [ ] Exclusion does not require a text explanation.
- [ ] Optional reason capture is available after exclusion.
- [ ] Generalized exception/pattern proposals require explicit approval and are never silent.
- [ ] Tests prove excluded emails are protected from the same rule in future runs.

## Blocked by

- GitHub issue `#46`
