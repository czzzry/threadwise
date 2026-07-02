# Add Rule Amendment Proposals from Exclusions

GitHub issue: `#49`

Parent: GitHub issue `#42`

## What to build

When exclusions reveal that a pending broader rule is too broad, Threadwise should propose a revised rule and recompute affected emails before apply.

Rule amendments are proposals only. Threadwise must never silently rewrite the rule.

## Acceptance criteria

- [ ] Multiple or semantically clear exclusions can trigger a proposed rule amendment.
- [ ] The proposal explains the revised boundary in plain English.
- [ ] The founder can accept, reject, or keep reviewing before the rule changes.
- [ ] Accepting an amendment recomputes the affected list and shows changed counts.
- [ ] Apply actions remain disabled while recomputing.
- [ ] If the boundary is unclear, Threadwise asks at most one clarifying question.
- [ ] Tests cover that rule amendments are not applied silently.

## Blocked by

- GitHub issue `#48`
