Status: implemented
Current as of: 2026-06-23

# Classify Amazon shipped updates as shopping-order

## Summary

Reduce the remaining Gmail unlabeled tail by classifying Amazon shipment updates that use the English `Shipped:` subject variant into the existing `shopping-order` taxonomy.

## Problem

Stored Gmail batches still contain reviewed unlabeled Amazon order updates whose sender and body clearly identify them as shipment notifications, but the current classifier misses the `Shipped:` subject wording.

## Goal

Make Amazon shipment updates with the `Shipped:` subject variant classify to `shopping-order`.

## Non-goals

- redesigning commerce heuristics broadly
- changing Gmail writeback behavior
- introducing any new taxonomy

## Acceptance criteria

- A focused classifier test proves `Shipped:` Amazon order updates classify to `shopping-order`.
- The classifier change is narrow and preserves existing order classification behavior.
- The relevant classifier suite passes after the change.

## Notes

- This is a thin whole-inbox-readiness cleanup slice discovered through the reviewed-unlabeled exception inspection added in issue 041.
