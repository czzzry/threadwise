# Core Flow Redesign and Model Labeling Handoff

Status: Complete; release candidate validated for `main`
Current as of: 2026-08-13
Superseded in part by: `docs/decisions/always-label-successfully-processed-mail.md` for initial model-label writes
Branch: `codex/threadwise-main-landing`

## Founder decisions

- Remove unsubscribe from the core product.
- Remove the destructive suspicious-sender action.
- Preserve List-Unsubscribe as a classification signal and suspicious as a review label.
- Support strong natural-language label correction, including exact multi-label changes.
- Make initial model labeling real, visible, review-only, and safe.
- Do not send, delete, Trash, Spam, archive, unsubscribe, block senders, or create provider filters during testing.
- Keep the approved compact Variant C Gmail-overlay direction.

## Implemented

- Removed user-reachable unsubscribe routes, cards, controls, and execution paths from the companion and legacy workbench.
- Removed the special suspicious-sender filter/label/Trash action; suspicious corrections use the ordinary non-destructive teaching seam.
- Added selected-email `only`, `add`, `remove`, and `replace` operations over one to three canonical labels.
- Preview shows ordered before/after labels, primary label, scope, and interpretation provenance.
- Apply consumes every approved label-change preview, including a one-label `only` change; it never reinterprets the approved intent.
- Gmail exact label-set replacement preserves unrelated labels, checks the live pre-write Threadwise-label baseline, and requires readback before reporting success.
- Initial model-assisted classification is enabled only by an explicit model plus API key. Model suggestions remain pending and cause zero automatic provider writes.
- Evidence distinguishes Rules, Model, Model abstained, and Model unavailable without exposing prompts, keys, or private content.
- The initial classifier runs once per fetched batch; the stored review queue reuses that result to avoid duplicate cost and provenance drift.
- Added a safe fresh-Mac setup guide and stronger tracked-file secret scanning.

## Validation

AUTOMATED:

- Repository suite: 842 tests passed, 16 skipped, both with the private model configuration present and with API keys deliberately absent.
- All companion JavaScript suites, the eight-case public demo, and public-data hygiene passed.
- Onboarding, contextual actions, selected explanation, coverage, queue navigation, and review progression controlled-browser gauntlets passed; review progression covered 42 contained responsive states with no forbidden provider requests.
- The Gmail coverage client uses bounded concurrent metadata reads and recognizes that an existing Gmail modify grant satisfies read-only coverage. A read-only grant still cannot authorize label writes.

LIVE:

- Passed on the founder's Mac using the production unpacked extension in authenticated real Gmail.
- A real model request passed using the machine-local OpenAI configuration; the key remains ignored, mode-restricted, and absent from Git.
- A reversible exact-label correction completed through Gmail and the original provider label set was verified after restoration.
- The explicit read-only coverage action completed in about 11 seconds, checked 72 current Inbox candidates, and produced a 64-item review queue. It performed no provider writes.
- The real minimized state collapses to one `Open Threadwise Home` control and preserves the 64-item queue count.
- Live Proton UI validation remains blocked because the disposable browser session is signed out of Proton Mail; no Proton provider write was attempted during this checkpoint.

## Deferred

- Multi-label future rules and matching-existing rewrites.
- Proton label removal/replacement.
- Flow F remains a product/design decision. Do not implement a dashboard/reporting expansion without founder approval of a visual prototype.
- Windows-specific startup polish is backlog only; the founder's intended daily host is macOS.
