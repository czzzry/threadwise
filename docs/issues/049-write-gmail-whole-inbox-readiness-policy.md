Status: implemented
Current as of: 2026-06-23

# Write Gmail whole-inbox readiness policy

## Summary

Write the explicit decision note that defines when the current bounded Gmail daily run is considered supervised-safe for daily whole-inbox use.

## Problem

The repo now proves a bounded Gmail daily run and the current reviewed-unlabeled frontier on stored founder-test Gmail data has been closed under the classifier. The remaining blocker is no longer message categorization. It is policy: the repo still needs a current, durable decision explaining what evidence is required before daily whole-inbox use is trusted, what residual manual-review burden is acceptable, and when the workflow should be paused.

## Goal

Capture the current Gmail whole-inbox readiness policy as a durable decision note without broadening the autonomy boundary.

## Non-goals

- adding new Gmail mutations
- changing the current low-value removal gate
- introducing a broad eval framework
- deciding scheduling or always-on syncing

## Acceptance criteria

- A current decision note defines the supervised-ready milestone for daily Gmail whole-inbox use.
- The note defines evidence gates, acceptable residual exception burden, and stop conditions that should pause daily use.
- The note explains how current `spam-low-value` trust should be interpreted.
- Current source-of-truth docs are updated so they do not still claim the readiness policy is missing.

## Notes

- This slice is documentation and policy only.
- It follows the completed inspection and classifier-cleanup slices under the current Gmail whole-inbox readiness PRD.
