# Issue 141 — Wire review-only model-assisted initial labeling

Status: Complete; automated and real-model LIVE acceptance passed
Current as of: 2026-08-13
Approved by: Founder, 2026-08-12
Parent direction: `docs/prd-threadwise-gauntlet-2026-08-09.md`

## Problem

The production Gmail companion currently starts with only the deterministic fixture classifier. The existing OpenAI runtime cascade is isolated in stored-corpus tooling, and its provenance does not reach Gmail batch artifacts or the Variant C review surface. Consequently, the live product cannot prove that its initial model labeler ran.

## Bounded outcome

Add an explicitly configured model-assisted classifier at the existing Gmail batch-classifier seam. Preserve deterministic classification as the no-model default. Persist a compact decision provenance record and show it under progressive disclosure in the selected-email review surface.

Model-generated initial suggestions remain pending for human review and must not auto-write Gmail in this slice. The read-only `Check Gmail` coverage service remains model-free.

## Acceptance criteria

- Companion startup creates the model classifier only when an explicit classification model and API key are configured.
- Missing model configuration preserves current deterministic behavior; a configured model with a missing key is visibly not ready rather than silently claiming model use.
- A model-reviewed message persists decision source, model name, confidence, abstention state, and rationale without storing keys, prompts, or extra private content.
- The Variant C explanation/details surface visibly distinguishes Rules, Model, model abstention, and model failure.
- Model suggestions are placed into the human review queue and cause zero Gmail label, Inbox, archive, Trash, Spam, unsubscribe, delete, or send actions before approval.
- Model error or abstention fails soft into pending review with truthful provenance.
- Coverage uses Gmail readonly behavior, makes no model call, and remains independent from classification.
- Controlled model-double tests prove the full companion path and zero Gmail writes.
- A real-model click-through pass requires local credentials and must show actual model provenance; if credentials are absent, it is reported BLOCKED rather than simulated.
- Focused tests and the repository-wide suite pass.

## Configuration contract

- API key: `EMAIL_AGENT_OPENAI_API_KEY`, with `OPENAI_API_KEY` as compatibility fallback.
- Initial classifier model: `THREADWISE_CLASSIFICATION_MODEL` or the corresponding explicit startup option.
- Teaching model: `THREADWISE_TEACHING_MODEL`.
- No paid model is selected implicitly for initial labeling.
