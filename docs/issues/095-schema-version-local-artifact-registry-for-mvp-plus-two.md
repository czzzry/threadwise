# Schema-version local artifact registry for MVP+2 artifacts

Status: Follow-up candidate
Type: Implementation
GitHub issue: `#20`
Parent: GitHub issue `#15`; `docs/local-data-retention-and-inbox-freshness-review-2026-07-01.md`

## What to build

Extend the local artifact registry and validation coverage to include the newer MVP+2 artifacts.

Current MVP+2 artifacts such as attention feedback, attention rules, dashboard run status, and the LLM usage ledger have local schema constants, but they are not fully represented in the central local artifact registry.

## Acceptance criteria

- [ ] Registers `attention_feedback.json`, `attention_rule_proposals.json`, `attention_rules.json`, `gmail_dashboard_run_status.json`, and `llm_usage_ledger.json`.
- [ ] Adds required-field validation for each registered artifact.
- [ ] Keeps attention daily-report schema validation aligned with `ATTENTION_SCHEMA_VERSION`.
- [ ] Provides focused tests for valid and invalid artifacts.
- [ ] Does not change artifact contents or migrate real local data in this slice.

## Safety boundaries

- Must not read private data contents outside synthetic tests.
- Must not mutate existing local artifacts.
- Any migration or rewrite should be a separate issue.

## Parallelization

Can run in parallel with `#18`. This is code-contract work and does not need live Gmail.
