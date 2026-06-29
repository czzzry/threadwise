# Handoff

Current as of: 2026-06-28

## Current source of truth

Read in this order before continuing:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md`
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. `docs/handoff/2026-06-28-review-priority-and-driver-status-tranche.md`
7. this handoff

## What changed in this tranche

- Added accepted-memory impact artifact generation:
  - `src/memory_impact_report.py`
  - `src/memory_impact_report_cli.py`
  - `scripts/build_memory_impact_report.py`
- The new artifact reports:
  - unresolved before vs after accepted memory
  - which accepted rules actually reduced backlog
  - top memory winners
  - next review payoffs from the current review pack
- Wired memory impact into the unattended safety triage pass:
  - `src/safety_triage_pass_cli.py`
  - `src/safety_triage_manifest.py`
  - `src/safety_triage_status.py`
  - `src/safety_triage_status_cli.py`
- Added storage paths:
  - `src/local_artifacts.py`
    - `memory_impact_reports_dir`
    - `memory_impact_report_path`

## Validation

New and updated targeted suites passed:

- `python3 -m unittest tests.test_memory_impact_report tests.test_memory_impact_report_cli tests.test_safety_triage_manifest tests.test_safety_triage_status tests.test_safety_triage_status_cli tests.test_safety_triage_pass_cli`
- Result: `8 tests OK`

Broader suites passed:

- `python3 -m unittest tests.test_shadow_review_pack tests.test_safety_backlog_report tests.test_safety_review_digest tests.test_safety_priority_pipeline tests.test_classifier_corpus_eval tests.test_classifier_corpus_eval_cli tests.test_frontier_compression tests.test_frontier_compression_cli tests.test_cluster_decision_pack tests.test_cluster_decision_pack_cli tests.test_runtime_cascade tests.test_runtime_cascade_cli tests.test_safety_disposition_store tests.test_memory_proposal_store tests.test_local_browser_review_ui`
- Result: `84 tests OK`

## Real artifact outcome

Regenerated downstream artifacts from the latest stored eval/frontier/digest inputs using the new code paths. New real artifacts:

- `data/classifier_eval/review_packs/shadow-review-pack-20260628T130754Z.json`
- `data/classifier_eval/safety_backlog_reports/safety-backlog-report-20260628T130754Z.json`
- `data/classifier_eval/memory_impact_reports/memory-impact-report-20260628T130912Z.json`
- refreshed `data/classifier_eval/latest_safety_triage_pass.json`

Current status output now shows:

- backlog pressure still `elevated`
- provider drivers:
  - `outlookmail` score `15`
  - `gmail` score `9`
  - `protonmail` score `3`
- accepted memory:
  - `53` rules
  - `53` impacted rules
  - unresolved before `1886`
  - unresolved after `1734`
- top memory winners are currently Outlook/Hotmail promo families, especially `Lieferando`

## Important interpretation

- This is the first artifact-backed proof that accepted memory is reducing the unresolved backlog at non-trivial scale.
- Outlook/Hotmail remains the biggest source of hard backlog and also the biggest source of memory gains right now.
- The next-review payoff ranking is still mechanically valid but not yet semantically strong enough for founder-facing prioritization, since the top payoffs currently show low-bucket items.

## Recommended next bounded step

Use the new memory-impact seam to improve payoff quality:

1. de-duplicate overlapping memory winners so the same sender/family is not overrepresented
2. strengthen next-review payoff ranking with:
   - provider backlog pressure
   - family size
   - safety priority
   - likely ambiguity reduction
3. surface a compact “review these next three” summary that is genuinely high value rather than merely first by current score
