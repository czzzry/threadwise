Status: implemented
Current as of: 2026-06-23

# Replay Gmail readiness across stored batches

## Summary

Add a local command that replays the current Gmail readiness policy across stored founder-test Gmail batches.

## Problem

The repo can now check one completed Gmail daily run from artifacts, but the founder also needs a broader answer from the local corpus already on disk: if the current classifier were replayed across the stored Gmail batches, would the residual exception burden still look safe enough for supervised daily use?

## Goal

Provide a local replay command that simulates current Gmail daily-run classification outcomes across stored Gmail batches without hitting Gmail again.

## Scope

- load stored Gmail batches for one account
- re-run the current classifier against each stored batch
- simulate the current auto-apply path from those refreshed suggestions
- evaluate the current per-run readiness thresholds across the stored batch sequence
- report the remaining reviewed-unlabeled frontier under the current classifier
- surface how much stored mutation evidence is real and verified versus missing

## Non-goals

- fetching new Gmail messages
- changing Gmail mutation behavior
- claiming that stored replay fully replaces live day-over-day operational proof
- broadening trust to unattended scheduling

## Acceptance criteria

- A local command can replay the current readiness thresholds across stored Gmail batches for one account.
- The command reports an overall pass, warn, or pause summary plus per-batch replay status.
- The command reports the current remaining reviewed-unlabeled frontier count from stored Gmail data.
- The command distinguishes verified mutation evidence from missing evidence and surfaces any stored mutation-policy violation as pause-worthy.
- The command works from the repo root without requiring manual `PYTHONPATH` setup.
