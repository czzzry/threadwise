# Decision Copilot UI Implementation Handoff

Status: Current implementation handoff
Current as of: 2026-07-11
Active branch: `codex/decision-copilot-ui`
Implementation checkpoint: `22740b4` (before this documentation update)
Pre-redesign backup: `codex/ui-before-decision-copilot-2026-07-11` at `9eef3d26e10448a91fb2a35359edf80e58a32173`
Approved direction: `docs/ui-ux-audit/2026-07-11-decision-copilot-direction.md`

## Outcome

Threadwise now presents the Gmail companion as a current-email Decision Copilot: one active job and at most one primary action per state. Current-email decisions complete before optional future learning or review of matching existing email. The simulator follows the same visible contract. The daily dashboard and unsubscribe review are separate, quieter supporting surfaces.

This was a UI/UX restructuring, not a new autonomy boundary. The label taxonomy, classifier semantics, Gmail mutation rules, candidate-evaluation promotion rules, analytics allowlist, and explicit unsubscribe-execution boundary remain intact.

## Source Of Truth

- Use `docs/ui-ux-audit/2026-07-11-decision-copilot-direction.md` for the approved interaction and visual contract.
- Use `docs/prd-async-threadwise-extension-2026-07-10.md` for preserved async companion behavior.
- Use `docs/analytics/tracking-plan.md` for the PostHog event and privacy boundary.
- Use `docs/handoff/2026-07-11-gmail-mutation-boundary.md` for durable Gmail write, partial-outcome, and retry behavior.
- Use the commits below and their tests as implementation evidence. Do not infer new scope from older UI plans or handoffs.

## Delivered Slices

- `c581633` records founder approval of the Decision Copilot direction.
- `378e0a0` through `601c770` implement the incremental harness, single-job shell, Review/Change/Preview/Applying/Receipt flow, exact partial outcomes, and post-receipt future-learning boundary.
- `70fed05` completes companion and simulator functional parity plus the associated mutation, duplicate-submit, queue, analytics, and failure-state safety fixes.
- `37ef9d7` applies the quieter editorial visual hierarchy and narrow-width header/layout fixes.
- `f3727f3` restructures and deduplicates the daily dashboard into Needs review, Activity, and Subscriptions.
- `0527203` replaces unsubscribe cards with a compact, selectable, local-only review list.
- `453898b` refines the dashboard's editorial hierarchy.
- `433ab92` makes the simulator acceptance fixture internally label-coherent.
- `53036aa` keeps affected-existing-email review in an expanded layout appropriate to the broader task.
- `22740b4` hardens inline candidate-key JSON against script termination and keeps selection save locked through the scheduled reload.

The root local harness intentionally retains its historical dense workbench because it is an internal acceptance surface. The shipped extension and product simulator use the Decision Copilot model.

## Preserved Safety Contracts

- Current-email changes default to `current-only`.
- Matching-existing-email changes remain a separate, explicit confirmation and are guarded against duplicate application.
- Saving a future candidate does not mutate Gmail.
- Complete and partial receipts state the label and Inbox outcomes truthfully; retry does not repeat a successful label write.
- The safe simulator disables Gmail checks and Gmail writes.
- Product analytics remain allowlisted and low-cardinality; the validator does not read email.
- Candidate evaluation remains pending until explicit evaluation and promotion; there is no automatic promotion.
- The unsubscribe review page changes local selection state only. It does not execute unsubscribe actions.
- Inline candidate keys cannot terminate their containing script, and selection save stays locked through the scheduled reload to prevent duplicate submission.
- ProtonMail remains read-only, and broad autonomous inbox actions remain out of scope.

## Validation Evidence

- Full Python suite: `605` tests passed.
- Focused Gmail companion UI suite: `73` tests passed, including inline candidate-key escaping and save/reload locking regressions.
- Gmail companion analytics JavaScript test passed.
- PostHog validator passed with `9` synthetic events and no email read.
- JavaScript syntax checks passed.
- Simulator CDP acceptance passed the complete state, duplicate-submit, confirmed-broad-apply, transport-failure, and `360`/`390`/`420` width matrix with `uncaughtErrorCount: 0`.
- Real in-app companion checks at `360`, `390`, and `420` pixels found no horizontal overflow and at most one primary action; the complete Review decision was visible at `420` pixels.
- Dashboard browser checks passed at desktop and `420` pixels with no overflow, exactly three default sections, and no Gmail-run form on the disabled simulator.
- Unsubscribe browser checks passed at desktop and `420` pixels for selection, save to Queued, and clear to Ready; the page showed one safety note and no execution action.
- Expanded existing-email review passed at `777` pixels with no document or table overflow.
- An earlier real-extension smoke passed Review to one `current-only` receipt request, then one future-save request; future learning made no Gmail change.
- A final extension CDP rerun could not open localhost because the execution environment returned `EPERM`. The script syntax still passed, and the earlier real-extension smoke, eighteen width audits, simulator parity checks, and safety review cover the affected contract.

## Reverting Or Comparing Safely

The backup branch is a fixed pre-redesign line. Do not reset, rebase, force-move, or delete it.

To inspect the old UI and then return to the redesigned UI:

```bash
git status --short
# Continue only when this prints nothing.

git switch codex/ui-before-decision-copilot-2026-07-11
git rev-parse HEAD
# Expected: 9eef3d26e10448a91fb2a35359edf80e58a32173

git switch codex/decision-copilot-ui
```

To resume work from the old UI without changing either named branch:

```bash
git status --short
# Continue only when this prints nothing.

git branch codex/ui-rollback-trial-2026-07-11 codex/ui-before-decision-copilot-2026-07-11
git switch codex/ui-rollback-trial-2026-07-11
```

Return at any time with:

```bash
git switch codex/decision-copilot-ui
```

## Next Stage

There is no active bounded PRD after this handoff. Use Threadwise in the real Gmail workflow, observe friction and the existing privacy-safe product analytics, and record concrete failures or repeated confusion. Choose the next bounded slice only after that evidence exists; do not extend the redesign from historical issue maps or speculative polish ideas.
