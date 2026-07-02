# Redesign Correct / Teach UX from Live Testing

GitHub issue: `#42`

## What to explore

The founder's live testing showed that the current correction flow is still too form-like and too verbose. Even after label inference, the product should likely move toward a simpler intent-first teaching surface with clearer action hierarchy and less explanatory text.

## Acceptance criteria

- [ ] Review the latest founder feedback notes around Komoot/newsletter/spam correction.
- [ ] Propose a simpler correction interaction model.
- [ ] Decide whether the dropdown should be secondary, hidden until needed, or replaced by suggested label chips.
- [ ] Decide how much explanation text belongs in the first visible state versus expandable detail.
- [ ] Break the approved redesign into bounded implementation issues.

## Partial grill decisions saved 2026-07-01

Founder paused the alignment session and asked to resume later. Do not re-ask these unless the founder explicitly wants to revisit them.

- The default teaching flow should be: fix the current email first, then suggest a broader rule if one can be inferred.
- When a broader rule is suggested, Threadwise should check whether that broader rule affects existing emails.
- Broader-rule preview should show count plus a plain-English rule first, with affected email examples behind a `Show affected emails` expander.
- Broader-rule impact should distinguish emails currently visible in Gmail inbox from older stored/archive emails.
- First implementation should use Threadwise's stored Gmail snapshot/inbox status for that split, not live Gmail search.
- Future note: revisit live Gmail confirmation/search later so broader-rule impact can reflect exact current inbox state once the UX is proven.

## Next open grill question

When Threadwise proposes `fix this email from A to B`, should applying that current-email fix require a distinct button such as `Apply to this email`, or should the preview confirmation itself apply it?

Current recommendation: use a distinct button, because preview should never mutate Gmail/local state.

## Blocked by

Needs founder/product alignment before implementation.
