Status: implemented
Current as of: 2026-06-23

# Classify Concilia MGM settlement notices as low value

## Summary

Reduce a remaining Gmail unlabeled exception family by classifying narrow `Concilia <no-reply@conciliainc.com>` MGM settlement notices into `spam-low-value`.

## Problem

Stored Gmail batches contain class-action settlement notices from `Concilia` about the MGM data incident. The founder does not want these notices kept in the manual exception path and prefers them to fall into low value.

## Goal

Make a narrow sender-aware rule so these `Concilia` MGM settlement notices classify to `spam-low-value`.

## Non-goals

- broadening low-value handling for every legal notice
- deciding a general policy for all class-action mail
- changing inbox-removal rules

## Acceptance criteria

- A focused classifier test proves the MGM settlement approval-hearing notice from `Concilia <no-reply@conciliainc.com>` classifies to `spam-low-value`.
- Existing safeguards that block false `job-related` classification continue to hold.
- The relevant classifier suite passes after the change.

## Notes

- This is a thin whole-inbox-readiness cleanup slice discovered through reviewed-unlabeled inspection.
- The rule is intentionally sender-aware and specific to the MGM settlement notice family.
