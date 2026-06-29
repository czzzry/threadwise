# Current Operating Model Checkpoint

Status: Current checkpoint
Current as of: 2026-06-29
Builds on: `docs/v2-alignment.md`
Current bounded PRD: `docs/prd.md` for the Gmail inbox companion release
Historical predecessors: `docs/archive/alignment-v1-gmail-mvp.md`, `docs/archive/prd-v1-gmail-mvp.md`, and `docs/archive/mvp-checkpoint-v1-issues-001-027.md`

This checkpoint is the short read for what Threadwise currently proves. The older MVP checkpoint stops at issues `001` through `027`; the repo now includes later slices through `039`.

## Current operating model

### Gmail

The Gmail path is now a usable supervised release workflow for one inbox:

1. fetch a fresh batch
2. classify messages into the approved taxonomy
3. auto-apply current suggested `EA/` labels
4. remove `INBOX` only for `promotions` and `spam-low-value`
5. write a daily report artifact
6. leave only unlabeled exceptions for manual follow-up
7. show the current email, compact daily summary, queue-preview path, teaching preview, and unsubscribe context in the Gmail companion sidebar during real inbox browsing

Manual browser review, explicit review/apply flows, retries, and local inspection commands remain available as fallback and verification paths.

The repo now also includes a deterministic live Gmail acceptance harness that can attach to the real Gmail page target, inject the sidebar when needed, and exercise queue-preview and teaching-preview flows against the founder's real inbox context.

### ProtonMail

The ProtonMail path is currently read-only:

1. fetch through Proton Mail Bridge or import a local export
2. normalize into the same provider-aware local batch model
3. classify messages and write daily report artifacts
4. leave unresolved exceptions for manual follow-up

No provider-side ProtonMail mutation is part of the current operating model.

### Reporting and workbench

The repo also supports:

- daily per-run operational reports
- weekly per-inbox analytical reports built from stored daily artifacts
- local browser workbench flows for exception review and unsubscribe work
- shadow-label evaluation against reviewed local data

## Proven slice map beyond the original MVP checkpoint

The original Gmail MVP checkpoint covered issues `001` through `027`.

Later implemented slices in the repo include:

- `028`: daily autonomous run with exception summary
- `029`: daily per-run operational report for one inbox
- `030`: weekly per-inbox analytical report from daily artifacts
- `031`: explicitly provider/account-aware run and report artifacts
- `032`: ProtonMail read-only fetch into the provider-aware batch model
- `033`: live ProtonMail read-only fetch via Bridge
- `034`: daily live ProtonMail read-only run with report
- `035`: Gmail unsubscribe inventory and selection workbench
- `036`: execute selected Gmail unsubscribes with audit
- `037`: manual follow-up path for unsupported unsubscribes
- `038`: split local browser review UI by responsibility
- `039`: formalize local batch report and audit data contracts

## Current safety and autonomy boundaries

Accepted bounded automation:

- auto-apply current suggested `EA/` labels
- remove `INBOX` only for Gmail messages labeled `promotions` or `spam-low-value`
- inventory unsubscribe candidates locally
- execute only supported unsubscribe actions that the user explicitly selected

Still out of scope by default:

- deleting mail
- trashing mail
- broad archiving
- unsubscribing without explicit user choice
- provider-side ProtonMail mutation
- background scheduling or always-on syncing

## What looks solid now

- Gmail daily run and exception-summary workflow
- Gmail companion sidebar as the primary supervised release surface
- live selected-email fallback into queue preview from unsynced Gmail messages
- live `Correct / Teach` preview path with broader-impact confirmation
- compact in-sidebar daily summary and unsubscribe surfacing
- daily and weekly report generation
- provider/account-aware local artifact handling
- ProtonMail read-only import and live Bridge paths
- unsubscribe inventory, supported execution, and manual follow-up
- browser review / inspection fallback tools
- shadow-label evaluation tooling
- maintenance work to split browser-review concerns and tighten local artifact contracts

## What still looks partial

- roadmap docs can still drift unless checkpoints and handoffs are refreshed
- ProtonMail write-side behavior is still unresolved product scope
- the local artifact model is central enough that it likely needs stronger explicit versioning and decision notes over time
- the isolated automation-browser path still relies on host-driven injection/message fulfillment for deterministic live Gmail acceptance instead of unpacked-extension parity by itself

## Next documentation needs

- explicit decision notes for provider-specific write boundaries
- clearer documented rules for unsubscribe safety and manual follow-up
- incremental-fetch and longer-lived operational decision notes if the founder wants to move from supervised runs toward a more persistent loop
