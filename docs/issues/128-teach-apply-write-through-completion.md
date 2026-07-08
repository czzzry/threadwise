# Teach / Apply Write-Through Completion

Status: Ready for agent after founder approval
Type: AFK
Parent PRD: `docs/prd-teach-apply-write-through-2026-07-07.md`
GitHub parent issue: `#58`

## What to build

Move the correction flow from local batch teaching into a visible apply-and-reload loop that the founder can trust.

The correction loop should become a small explicit state machine:

1. draft intent
2. proposed rule
3. accepted rule
4. scope choice
5. applying
6. compact receipt

Within that loop, the correction decision should expose three explicit outcomes:

1. apply once
2. apply once + future
3. apply once + future + inbox

The first option only changes the current email. The second option also saves the rule for future matching mail. The third option also rewrites matching existing inbox mail through Gmail write-through.

The visible result should make it clear what changed locally and what changed in the inbox after refresh. Failed actions must preserve the draft/accepted rule text so the founder can retry without retyping.

## Acceptance criteria

- [ ] The correction path presents the three scope choices as the primary outcomes using concise CTAs:
  - `Fix email`
  - `Fix + future`
  - `Fix + inbox`
- [ ] The correction path first shows `Proposed rule:` and requires accept/edit before scope selection.
- [ ] `Edit` changes the proposed rule itself, not a separate hint prompt.
- [ ] Clear edited rules are accepted directly; ambiguous edited rules are reformulated once for confirmation.
- [ ] `Fix email` updates only the current email result.
- [ ] `Fix + future` also saves the rule for future mail.
- [ ] `Fix + inbox` rewrites matching existing inbox mail through Gmail write-through using the accepted rule as the match definition.
- [ ] Matching remains conservative by default and does not broaden to all domain mail unless the accepted rule explicitly does so.
- [ ] The result state states exactly which scope changed using compact operational copy.
- [ ] Failed apply preserves the draft/accepted rule text for retry.
- [ ] Reloading the companion after apply reflects the updated local state instead of the stale email.
- [ ] The empty home state is minimal and does not preload a previously reviewed email.
- [ ] Large inbox runs show the estimated match count before execution.
- [ ] Large inbox runs require explicit inline confirmation when the estimate exceeds `200`.
- [ ] The current-email path remains the simplest path and does not require the founder to think about inbox scope unless they choose it.

## Notes

This slice intentionally moves the product toward the founder's desired end state: teach a rule, apply it, clear the `needs check` items, reload, and see the inbox reflect the rule.

Implementation order inside the slice:

1. teach-state machine reset and empty home state
2. scope actions, running states, and compact receipts
3. full-inbox write-through and bulk confirmation
