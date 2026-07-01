# Generate Gmail attention candidates with LLM

Status: Ready for agent
Type: AFK
GitHub issue: `#9`
Parent: GitHub issue `#7`; `docs/prd.md`

## What to build

Build the separate Gmail attention evaluator and wire it into the daily Gmail run so confirmed runs can produce Needs attention candidates in the daily report.

The evaluator should inspect all newly processed Gmail messages plus a bounded stored lookback, use compact payloads by default, batch messages where practical, and perform at most one full-body second pass for high-consequence ambiguous candidates.

## Acceptance criteria

- [ ] Attention evaluation is separate from classification and does not change classification labels.
- [ ] The evaluator supports `needs_attention_now`, `possible_attention`, `not_attention`, and `insufficient_context`.
- [ ] The evaluator supports MVP+2 categories: travel, bill due, account risk, security, reply deadline, appointment, and job opportunity.
- [ ] The evaluator considers all newly processed Gmail messages, not just unlabeled exceptions.
- [ ] The evaluator fills remaining capacity from stored local lookback, latest batch first, with a default cap of 50 evaluated messages.
- [ ] Compact payloads are used by default.
- [ ] A single full-body second pass is allowed only for high-consequence ambiguous candidates.
- [ ] Attention detection is fail-soft and non-mutating.
- [ ] Tests use fake model clients and do not call live OpenAI or Gmail.

## Blocked by

- GitHub issue `#8`; `docs/issues/083-add-gmail-attention-contract-to-daily-report.md`
