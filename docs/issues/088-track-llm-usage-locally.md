# Track LLM usage locally

Status: Completed
Type: AFK
GitHub issue: `#13`
Parent: GitHub issue `#7`; `docs/prd.md`
Completed in: `c820b8d`

## What to build

Add a generic local LLM usage tracker and wire it first to Gmail attention detection.

The founder wants a lightweight answer to "how much is Threadwise spending on LLMs?" without building a full observability platform. The tracker should record token usage and estimated cost per feature/run, then expose simple daily, weekly, and monthly summaries.

This slice can run in parallel with attention evaluator and dashboard work after the attention report contract exists. The generic ledger and summary helper can be built first; the final attention write-through should coordinate with the evaluator slice.

## Acceptance criteria

- [x] A generic local usage event contract records timestamp, feature, model, input tokens, output tokens, estimated cost, and run id.
- [x] Gmail attention detection writes usage events.
- [x] The daily report attention section includes relevant usage metadata for that run.
- [x] A summary helper can report usage by day, week, month, and feature.
- [x] The dashboard or report can show a compact "today/month" attention LLM cost summary.
- [x] Cost estimates are clearly treated as estimates, not billing truth.
- [x] Tests cover usage event recording and summary aggregation.

## Blocked by

- GitHub issue `#8`; `docs/issues/083-add-gmail-attention-contract-to-daily-report.md`
- Final attention write-through also depends on GitHub issue `#9`; `docs/issues/084-generate-gmail-attention-candidates-with-llm.md`
