# CONTEXT.md

Status: Current repo context
Current as of: 2026-08-20

This file is the short "you are here" guide for the repo.

Its job is to stop agents or future sessions from treating old planning docs as current instructions.

If this file becomes stale, update it or remove it. Do not keep it as ceremonial documentation.

## What This File Is For

Use `CONTEXT.md` to answer four questions quickly:

1. What stage is the repo in now?
2. Which docs are current?
3. Which docs are historical?
4. What trust boundaries still matter?

## Read Order

Before substantial planning or implementation work, read:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. the current bounded PRD, if one exists
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. the relevant current issue, if one exists

Do not infer approval from `docs/v2-issue-map.md`, archived PRDs, or old handoffs alone.

## Current Stage

The founder has approved the Threadwise World-Class Triage Gauntlet in `docs/prd-threadwise-gauntlet-2026-08-09.md`. It preserves the existing Threadwise logo and Gmail-overlay architecture, excludes AI auto-response and writing, and uses Mail-0/Zero, Grammarly, Refined GitHub, Raycast, and Linear as the specified functionality and interaction bars.

On 2026-08-11 the founder approved the real-Gmail Variant C production visual milestone and a truthful provider-coverage slice: a selected message or narrow local snapshot must never be presented as the whole inbox. Slice 7 is complete, including an explicit read-only coverage refresh, controlled-browser acceptance, and live Gmail verification. On 2026-08-20 the action became the provider-neutral `Check inbox` and gained Proton Mail support. Selected-message handling and provider coverage remain separate axes, and coverage never routes through provider mutation behavior.

The Gauntlet is decomposed in `docs/threadwise-gauntlet-slice-map-2026-08-09.md`. Implementation still proceeds one triaged vertical slice at a time. The first-run companion slice in issue `#105` is implemented and won its second independent critic round at `97/100`; see `docs/handoff/2026-08-09-threadwise-gauntlet-onboarding.md`. Queue-local search and panel-scoped keyboard navigation in issue `#106` is also complete: its fourth fresh critic declared a WIN at `85/100` versus the documented `~70/100` baseline after real focus, nonzero-scroll, and explicit-exit corrections. See `docs/handoff/2026-08-09-threadwise-gauntlet-queue-navigation.md`. The contextual action panel in issue `#107` is complete: its third fresh critic declared a WIN at `94/100`, approximately `+24` over baseline, after closed-loop scroll/focus and collision-aware placement corrections. See `docs/handoff/2026-08-09-threadwise-gauntlet-contextual-actions.md`. Selected-email explanation and one-click correction in issue `#108` is also complete: its first fresh critic declared a WIN at `87/100`, `+17` over baseline, with five of six tasks and all safety gates clear. See `docs/handoff/2026-08-09-threadwise-gauntlet-selected-email-explanation.md`. High-throughput review completion in issue `#109` is now complete: its final fresh critic declared a WIN at `96/100` versus the documented `~70/100` baseline after every direct and chained late-response boundary was anchored to the live provider, message, thread, URL, and route. See `docs/handoff/2026-08-09-threadwise-gauntlet-review-progression.md`.

On 2026-08-12 the founder removed unsubscribe and the destructive suspicious-sender action from the core product. List-Unsubscribe remains only as a classification signal and `suspicious` remains a review label. The selected-email corrector supports truthful one-to-three-label `only`, `add`, `remove`, and `replace` changes for the current email, executes the approved preview without a second model interpretation, and checks Gmail's live Threadwise-label baseline before replacement.

On 2026-08-20 the founder replaced the review-only model-write restriction with the always-label decision in `docs/decisions/always-label-successfully-processed-mail.md`. Every successfully processed message now receives Threadwise's best one-to-three labels in Gmail or Proton Mail. Low-confidence model decisions remain pending for review after the additive label write. Read-only coverage discoveries request a real classification sync and never create unlabeled review items; old coverage-only batches are excluded from runtime queues. Genuine model, provider-read, or provider-write failures remain visible operational exceptions rather than ordinary unlabeled review work.

The current implementation passes 848 repository tests with 16 expected skips, all extension JavaScript behavior suites, public-data hygiene, and real browser click-throughs of the shared Proton coverage, sync, review, correction, and minimized states. The installed companion is healthy, its configured initial and teaching models are ready, Proton Mail Bridge is available, and the scheduled Proton entry point loads the same private model configuration as the companion.

LIVE Gmail now passes on the founder's Mac with the production unpacked extension and local companion. The configured OpenAI model is available without exposing its key. A reversible exact-label correction was verified against Gmail and restored to its original label set. The explicit read-only coverage check completed in about 11 seconds, checked 72 current Inbox candidates, and produced a 64-item review queue without changing provider labels. The minimized state exposes one `Open Threadwise Home` control and preserves the queue count. See `docs/handoff/2026-08-12-core-flow-redesign-and-model-labeling.md`.

The universal Threadwise experience in `docs/prd-universal-threadwise-experience-2026-08-01.md` is implemented behind one minimized-by-default browser side panel for Gmail and ProtonMail. The two inboxes remain provider-scoped, while review, teaching, scope selection, optimistic advancement, background writes, retry, and activity use one implementation.

Automated and synthetic-browser acceptance is complete. One live Proton selected-message acceptance check remains before the old `/proton-review` fallback is removed; live-provider writes remain separately approval-gated.

Threadwise is past basic MVP proof.

The repo already proves:

- Gmail daily run flows with bounded Gmail mutation
- browser-based Gmail companion flows
- dashboard and workbench surfaces
- historical local unsubscribe artifacts retained without any current review or execution surface
- ProtonMail read paths plus a bounded Bridge-backed, label-only review console
- local artifact, reporting, and review tooling
- a public no-login demo that runs entirely on synthetic browser-local data

The current branch state includes the completed async Gmail companion extension slices `133` through `137`, including:

- visible selected-email understanding states
- explicit async teach / fix lifecycle states
- background follow-up refresh off the main response path
- compact recent-activity and retry visibility
- a founder-facing teaching pack for this async architecture

The current architecture checkpoint is documented in `docs/handoff/2026-08-01-universal-threadwise-provider-parity.md`. Rendering and browser behavior are shared, provider page access sits behind browser adapters, ordered writes use one queue implementation, and backend teaching plus companion lifecycle behavior now sits behind a provider runtime registry. The earlier module-extraction history remains in `docs/handoff/2026-07-20-architecture-refactor-closeout.md`.

The personal Mac now also has a native `Threadwise Control` menu-bar app. It reports the local companion as Running, Stopped, or Needs attention; safely disables and unloads the KeepAlive LaunchAgent when stopped; re-enables it when started; reports whether Proton Mail Bridge is required but unavailable; and manages the incremental 6:00 a.m. Proton daily schedule. See `docs/threadwise-menu-bar-control.md`, `docs/handoff/2026-08-05-threadwise-menu-bar-service-control.md`, and `docs/handoff/2026-08-05-proton-sync-recovery.md`.

## Current Source Of Truth

For the active Gauntlet direction and bounded slice, use:

1. `docs/prd-threadwise-gauntlet-2026-08-09.md`
2. `docs/threadwise-gauntlet-slice-map-2026-08-09.md`
3. `docs/decisions/always-label-successfully-processed-mail.md` for the current initial-label and review-queue contract
4. `docs/handoff/2026-08-12-core-flow-redesign-and-model-labeling.md` with issues `#139`, `#140`, and `#141` for the completed safety, exact-label correction, and historical review-only model-labeling amendment
5. `docs/handoff/2026-08-09-threadwise-gauntlet-review-progression.md`, `docs/issues/109-make-optimistic-review-advancement-truthful.md`, and GitHub issue `#109` for the completed high-throughput review-completion slice
6. `docs/handoff/2026-08-09-threadwise-gauntlet-selected-email-explanation.md`, `docs/issues/108-attach-truthful-explanation-and-one-click-correction.md`, and GitHub issue `#108` for the completed selected-email explanation slice
7. `docs/handoff/2026-08-09-threadwise-gauntlet-contextual-actions.md`, `docs/issues/107-add-contextual-action-panel-to-companion.md`, and GitHub issue `#107` for the completed contextual-action slice
8. `docs/handoff/2026-08-09-threadwise-gauntlet-queue-navigation.md`, `docs/issues/106-add-queue-filtering-and-panel-keyboard-navigation.md`, and GitHub issue `#106` for the completed queue-local interaction slice
9. `docs/handoff/2026-08-09-threadwise-gauntlet-onboarding.md` and GitHub issue `#105` for the completed first-run onboarding slice
10. `docs/v2-alignment.md`
11. `docs/prd-universal-threadwise-experience-2026-08-01.md` for the shared-provider architecture and safety baseline

For the next provider-parity milestone, use:

1. `docs/prd-universal-threadwise-experience-2026-08-01.md`
2. `docs/v2-alignment.md`
3. the implementation issues created from that PRD after bounded slicing

For the just-completed async extension work, use:

1. `docs/prd-async-threadwise-extension-2026-07-10.md`
2. `docs/issues/133-add-async-selected-email-understanding-states.md`
3. `docs/issues/134-add-async-action-lifecycle-for-teach-and-fix.md`
4. `docs/issues/135-move-slower-follow-up-work-off-the-main-sidebar-path.md`
5. `docs/issues/136-add-recent-activity-and-retry-surface-for-async-operations.md`
6. `docs/issues/137-build-comprehensive-teaching-pack-for-async-threadwise-extension.md`

For the founder-approved bounded Proton review-console experiment, use `docs/issues/138-add-proton-bridge-review-console.md`. It is the authority for the narrow label-only Proton write boundary.

For the current implementation architecture, use `docs/handoff/2026-08-01-universal-threadwise-provider-parity.md`. Use `docs/handoff/2026-07-20-architecture-refactor-closeout.md` only for the earlier module-extraction history.

For repo workflow and guardrails, use `AGENTS.md`.

For broader product direction, use `docs/v2-alignment.md`.

## What Is Historical

Treat these as historical unless explicitly pulled back into an active slice:

- `docs/v2-issue-map.md`
- old handoffs in `docs/handoff/`
- archived PRDs and planning docs in `docs/archive/`
- older completed slice docs that describe already-shipped states rather than the current bounded task

Historical docs are still useful context. They are not approval.

## Trust Order When Docs Differ

Use this order:

1. current task-specific PRD or triaged issue
2. `AGENTS.md`
3. `CONTEXT.md`
4. `docs/v2-alignment.md`
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. archived docs and handoffs as background only

## Current Trust Boundaries

- Gmail mutation must stay bounded and auditable
- Gmail and Proton Mail runs add the best available Threadwise labels for every successfully processed message. Low-confidence decisions remain pending for review after the additive write. Genuine classification or verification failures are operational exceptions, not ordinary unlabeled queue items.
- Proton Mail writes are verified through Bridge and preserve Inbox. No Proton label replacement, move, archive, Trash, Spam, send, or provider rule changes are allowed.
- unsubscribe execution is not part of the current core product
- broad autonomous inbox actions remain out of scope by default
- private email, credentials, OAuth, and live inbox data remain sensitive

## Maintenance Rule

Update this file when one of these changes:

- the active bounded PRD changes
- the current milestone or implementation slice changes
- the trust order changes
- the file starts pointing at stale "current" work

If nobody is willing to maintain it, delete it and remove the read-order dependency from `AGENTS.md`.
