Status: implemented
Current as of: 2026-06-23

# Close final reviewed-unlabeled singletons

## Summary

Close the final reviewed-unlabeled singleton messages discovered during Gmail whole-inbox readiness cleanup.

## Problem

After the recurring-family cleanup slices, only a small set of reviewed-unlabeled singleton messages remained under the current classifier. They still block a clean whole-inbox readiness picture even though the founder has now given explicit label intent for each one.

## Goal

Classify the final singleton messages into the existing taxonomy using narrow sender-aware rules.

## Label decisions

- LinkedIn report-status acknowledgement -> `spam-low-value`
- iNaturalist event / engagement nudge -> `spam-low-value`
- xAI API product announcement -> `spam-low-value`
- Coursera / University of Michigan course promo -> `spam-low-value`
- Prime Video subscription-ended notice -> `shopping-order`
- Przelewy24 transaction notice family -> `spam-low-value`

## Non-goals

- broadening generic rules for all social, education, or transaction emails
- introducing a new phishing-specific taxonomy bucket
- changing inbox-removal rules

## Acceptance criteria

- Focused classifier tests prove the six singleton shapes above classify to the intended existing labels.
- The relevant classifier suite passes after the change.
- Re-running the current reviewed-unlabeled gap check leaves no remaining unlabeled singleton from the current frontier.

## Notes

- `Prime Video` is treated as retrieval-useful subscription state, not low-value.
- `Przelewy24` is intentionally routed to `spam-low-value` under the current taxonomy because the founder considers this family dangerous or irrelevant and wants it out of the manual exception path.
