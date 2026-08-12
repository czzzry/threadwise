# Core Flow Redesign and Model Labeling Handoff

Status: Automated implementation complete; LIVE Gmail gate blocked
Current as of: 2026-08-12
Branch: `codex/threadwise-coverage-implementation`

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

- Repository suite: 825 tests passed, 16 skipped.
- Focused correction, teaching, initial-classifier, and companion UI suites passed.
- Relevant JavaScript suites and syntax checks passed.
- Public-data hygiene checks passed before the final integration correction and remain part of the final publish gate.

LIVE:

- Not passed and not substituted with synthetic evidence.
- Gmail OAuth artifacts exist locally, but `.env`, the OpenAI API key, and model configuration are absent.
- Windows desktop control stopped before Gmail interaction because it could not verify the active Brave URL safely.
- No Gmail/provider mutation was attempted in this checkpoint.

## Required LIVE follow-up

On a founder-present machine with the unpacked extension loaded, a configured teaching and classification model, and a designated non-sensitive Gmail test set:

1. Record each message's Threadwise labels, Inbox state, unread state, star, and importance.
2. Exercise current-email `only`, exact two-label, add, remove, and replace corrections; confirm preview equals provider result and the model is not called again on Apply.
3. Exercise ambiguous, contradictory, and unknown-label notes; confirm zero provider effect.
4. Run initial classification on representative messages and confirm visible real model name/provenance, pending review, and zero automatic writes.
5. Restore every test message to the recorded state and verify restoration by rereading Gmail.
6. Capture equivalent screenshots and interaction evidence. Do not claim LIVE until this completes.

## Deferred

- Multi-label future rules and matching-existing rewrites.
- Proton label removal/replacement.
- Flow F remains a product/design decision. Do not implement a dashboard/reporting expansion without founder approval of a visual prototype.
- Windows-specific startup polish is backlog only; the founder's intended daily host is macOS.
