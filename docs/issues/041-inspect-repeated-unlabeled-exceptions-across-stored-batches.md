# Status

Implemented on 2026-06-23
Current as of: 2026-06-23
Triage state: `implemented`
Builds on: `docs/prd.md`
Blocked by: None

# Title

Inspect repeated unlabeled exceptions across stored batches

## Type

AFK

## User-visible goal

Show the founder which reviewed unlabeled Gmail exceptions recur across stored batches, so the next classifier or workflow slices can target the highest-value manual-review pain first.

## Scope

- Read stored local batch artifacts for one account
- Consider reviewed unlabeled items only
- Group repeated exceptions into privacy-safe recurring clusters
- Rank clusters by recurrence count
- Show representative batch references and lightweight examples for each cluster
- Keep the first slice local, inspectable, and read-only

## Non-goals

- Changing Gmail mutation behavior
- Reclassifying messages automatically
- Solving every exception cluster in the same slice
- Large browser UI redesign
- Background scheduling
- Cross-provider unification

## Acceptance criteria

- A local command can inspect stored batches for one account and summarize repeated reviewed unlabeled exceptions.
- The summary excludes pending items and excludes already labeled reviewed items.
- The summary groups recurring exceptions with stable counts and references to recent source batches.
- The output stays privacy-safe and does not dump full raw message bodies.
- Empty storage and accounts with no reviewed unlabeled exceptions are handled cleanly.

## Expected behavior

- The founder can run one local inspection command after prior daily runs and see the top recurring reviewed unlabeled exception clusters.
- Each cluster includes enough context to decide whether it is a classifier gap worth a follow-on slice.
- The slice does not mutate Gmail, does not alter stored review decisions, and does not broaden autonomy.

## Expected tests or verification

- Add a storage-backed CLI test modeled on the local batch index/status suites.
- Test grouping across multiple stored batches for the same account.
- Test that pending items and reviewed labeled items are excluded.
- Test privacy-safe output and clean empty-state behavior.
- Re-run the new suite plus the relevant existing local inspection tests.

## Dependencies/order

- This is the first implementation slice under the current Gmail whole-inbox readiness PRD.
- It should complete before new classifier cleanup slices, because it tells the repo which unlabeled patterns matter most now.

## Stop conditions requiring Founder review

- The slice starts guessing new labels instead of inspecting exceptions.
- The grouping requires exposing more private message content than the current inspection commands already reveal.
- The work starts expanding into scheduling, autonomy policy, or cross-provider scope.
