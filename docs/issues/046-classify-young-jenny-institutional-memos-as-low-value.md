Status: implemented
Current as of: 2026-06-23

# Classify Young/Jenny institutional memos as low value

## Summary

Reduce a remaining Gmail unlabeled exception family by classifying narrow `Young, Jenny <youngje@gbgh.on.ca>` institutional memos into `spam-low-value`.

## Problem

Stored Gmail batches contain `GBGH` work-style memos from a sender the founder does not recognize and does not consider relevant to their inbox. These messages should not remain in the manual exception path.

## Goal

Make a narrow sender-aware rule so these `GBGH` memo-style messages classify to `spam-low-value`.

## Non-goals

- broadening low-value handling for every hospital or workplace domain
- deciding a general work-memo taxonomy
- changing inbox-removal rules

## Acceptance criteria

- A focused classifier test proves `GBGH Information: ED Team Mailboxes` from `Young, Jenny <youngje@gbgh.on.ca>` classifies to `spam-low-value`.
- A focused classifier test proves `GBGH Memo - Temporary Pause of Gynecological Services - Dr. Agboola` from the same sender classifies to `spam-low-value`.
- The relevant classifier suite passes after the change.

## Notes

- This is a thin whole-inbox-readiness cleanup slice discovered through reviewed-unlabeled inspection.
- The rule is intentionally sender-aware and conservative because the founder explicitly wants these messages treated as low value even if they are legitimate institutional mail.
