Status: implemented
Current as of: 2026-06-23

# Check Gmail readiness from daily run artifacts

## Summary

Add a local command that checks whether a Gmail daily run still satisfies the current whole-inbox readiness policy.

## Problem

The repo now has an explicit Gmail whole-inbox readiness policy, but it still takes manual inspection to decide whether a specific run stayed inside the acceptable thresholds and artifact rules.

## Goal

Provide a local readiness-check command that evaluates one Gmail daily run against the current policy using stored artifacts only.

## Scope

- read Gmail daily report artifacts for one account
- inspect the target run, defaulting to the latest Gmail daily report for that account
- evaluate run-level thresholds from the current readiness policy
- verify that required write and inbox-removal artifacts exist and are internally consistent
- surface a clear status such as pass, warn, or pause

## Non-goals

- changing Gmail mutation behavior
- re-running Gmail fetches
- evaluating the historical reviewed-unlabeled frontier automatically
- deciding unattended scheduling

## Acceptance criteria

- A local command can evaluate one Gmail daily run for one account and report pass, warn, or pause.
- A run within thresholds and with consistent artifacts reports pass.
- A single threshold breach reports warn.
- consecutive threshold breaches or mutation/artifact inconsistencies report pause.
- The command works from the repo root without requiring manual `PYTHONPATH` setup.
