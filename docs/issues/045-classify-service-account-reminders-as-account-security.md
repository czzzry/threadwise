Status: implemented
Current as of: 2026-06-23

# Classify service account reminders as account-security

## Summary

Reduce the remaining Gmail unlabeled tail by classifying a narrow set of high-signal service account reminders into the existing `account-security` taxonomy.

## Problem

Stored Gmail batches still contain reviewed unlabeled account notices such as password-exposure alerts and linked-service consent reminders. These are important retrieval messages and should not stay in the manual exception path.

## Goal

Make narrow, sender-aware service account reminders classify to `account-security`.

## Non-goals

- broadening account heuristics to generic service updates
- changing inbox-removal rules
- adding any new taxonomy

## Acceptance criteria

- A focused classifier test proves Duolingo password-exposure notices classify to `account-security`.
- A focused classifier test proves Google linked-services consent reminders classify to `account-security`.
- The relevant classifier suite passes after the change.

## Notes

- This is a thin whole-inbox-readiness cleanup slice discovered through the reviewed-unlabeled exception inspection added in issue 041.
