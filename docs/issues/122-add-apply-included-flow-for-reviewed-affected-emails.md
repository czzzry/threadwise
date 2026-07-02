# Add Apply-Included Flow for Reviewed Affected Emails

GitHub issue: `#48`

Parent: GitHub issue `#42`

## What to build

After affected emails have been reviewed, let the founder apply the broader rule only to exact included IDs, while saving the future rule and durable exceptions.

The apply result should report exactly what changed.

## Acceptance criteria

- [ ] Expanded review mode exposes `Apply to included` only when the affected set is current.
- [ ] `Apply to included` applies only to exact included message IDs.
- [ ] The future rule is saved as part of the normal apply-included flow.
- [ ] Durable exceptions for excluded emails are preserved.
- [ ] The success state reports counts for emails updated, exceptions saved, and future rule saved.
- [ ] Applying is disabled while affected emails are stale or recomputing.
- [ ] The decision is recorded in the local audit trail.
- [ ] No `apply once only` primary flow is introduced.

## Blocked by

- GitHub issue `#47`
