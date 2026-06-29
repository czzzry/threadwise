Status: Current operational-readiness note
Current as of: 2026-06-29
Builds on: `docs/prd.md`, `docs/handoff/2026-06-29-slice-2-unified-operator-loop.md`

# Purpose

This note defines the current simple operational question for the multi-inbox classifier loop:

> Are repeated recent runs staying stable enough that the founder can trust the loop daily without runaway unresolved work or review debt?

# Current report

Use:

`python3 scripts/check_operational_readiness.py`

The report reads recent runtime-cascade runs plus the unified review queue and returns:

- `PASS`
- `WARN`
- `PAUSE`

The unified review queue now also includes hotspot-derived founder questions for the biggest recurring unresolved families, so readiness reflects not just raw unresolved volume but whether the next best cleanup work is already staged in the operator loop.

# What the current status means

## `PASS`

Recent runs look stable enough by the current thresholds:

- at least 3 recent runs are available
- latest unresolved rate is below `10%`
- queue debt is not too high
- founder question load is not too high
- at least one founder-answer application exists, proving the feedback loop has been exercised

## `WARN`

The loop still works, but the operational evidence is not yet strong enough to trust it casually every day.

Typical reasons:

- too few recent runs
- unresolved rate is still above the `10%` target and above the current warning band
- queue debt is still noticeable
- founder is being asked too many questions at once
- no real founder-answer applications have been recorded yet

## `PAUSE`

The loop is accumulating too much risk or debt and should be treated as unstable until corrected.

Typical reasons:

- unresolved rate is too high
- queue debt is too high
- repeated runs are drifting in the wrong direction

# Current founder budget

Current founder-question budget:

- tolerate up to `20` pending founder questions at once before warning

# Progress readout

The readiness report also now shows:

- current unresolved count vs target unresolved count on the latest corpus
- remaining unresolved gap in messages
- founder-question count vs founder-question limit

# Current threshold style

These thresholds are intentionally simple and product-facing, not statistically fancy.

They are meant to answer:

- should we keep trusting the current supervised loop?
- are we reducing work or just moving it into a backlog?
- is the founder review load staying bounded?

The thresholds may be tightened later once repeated real daily runs exist.
