# Threadwise Gauntlet handoff: selected-email explanation

Status: Slice complete; first fresh critic WIN at 87/100
Current as of: 2026-08-09
Issue: `#108`
Parent: `#104`
Branch: `codex/threadwise-gauntlet`
Starting implementation commit: `8f7b1c4`

## Outcome

Threadwise now explains a selected review email where the decision is made: suggested label, exact queue reason, stored uncertainty band, and stored rationale appear in one compact block before the primary/correction actions. Secondary stored evidence is collapsed. The handled-receipt `Why` action uses the same model.

The implementation uses no new AI call or provider route. It performs no mailbox action, and it adds no email writing behavior.

## What changed

- `src/gmail_companion_state.py`
  - adds an interpretation-only `rationale`
  - normalizes stored confidence to `high`, `medium`, `low`, or empty
  - filters and deduplicates stored near misses to canonical labels
- `extensions/gmail_companion/selected_explanation.js`
  - derives truthful review/handled presentation copy
  - keeps provider recovery separate from uncertainty
  - allowlists progressive evidence rows
- `extensions/gmail_companion/content.js`
  - renders the explanation in review and handled `Why`
  - preserves direct `Accept` / `Apply`, `Change label`, and `Change`
  - restores disclosure focus without touching generic technical-detail focus
  - resets disclosure state on selected-message changes
- `extensions/gmail_companion/manifest.json`
  - loads the pure policy before the content script
- focused Node/Python tests and a controlled CDP validator cover policy, normalization, real pixels, stale context, focus, scroll, and request boundaries
- prior queue/context-action validators load the new module so their regression paths remain executable

## Validation

- `node tests/gmail_companion_selected_explanation_test.js` — PASS
- `node tests/gmail_companion_context_actions_test.js` — PASS
- `node tests/gmail_companion_queue_navigation_test.js` — PASS
- `node scripts/validate_threadwise_selected_explanation_cdp.mjs http://127.0.0.1:9222` — PASS
- `node scripts/validate_threadwise_context_actions_cdp.mjs http://127.0.0.1:9222` — PASS
- `node scripts/validate_threadwise_queue_navigation_cdp.mjs http://127.0.0.1:9222` — PASS
- `python3 -m unittest discover -s tests` — PASS, `797/797`
- `git diff --check` — PASS

Controlled selected-explanation evidence:

- `/tmp/threadwise-selected-explanation/selected-explanation-trace.json`
- 18 PNGs for high-confidence review, low-confidence/no-label review, missing evidence, write-unconfirmed recovery, queue preview, and handled `Why`
- three viewports per state: `1280x800`, `756x469`, `360x800`
- 22 allowed state-read/observer requests
- zero unexpected requests
- Gmail-page scroll remains `180`; companion scroll remains `72` across disclosure open

## Critic result

The separate fresh-context critic inspected every current screenshot, source changes, selected trace, queue trace, and contextual-action trace. Blind A/B was not practical; it compared directly with pre-slice commit `49c12fe`.

- Verdict: **WIN**
- Score: `87/100`
- Baseline: `~70/100`
- Delta: `+17`
- Fixed tasks: `5/6`
- Hard gates: all clear
- Largest residual: at `756x469`, short-viewport review states may require scrolling before the full correction control is visible; the surface remains contained and directly correctable, but this is the strongest remaining polish gap.

## Boundaries preserved

- approved logo unchanged
- Gmail/Proton overlay architecture unchanged
- no separate inbox or replacement mail client
- no compose, draft, reply, forward, send, or auto-response
- no classifier call, credential, provider endpoint, live inbox access, provider write, or new mailbox action
- shared provider-neutral presentation; Gmail remains only the controlled synthetic host

## Next bounded step

Triage slice 5, high-throughput review completion, before implementation. Preserve issues `#106` through `#108` as the interaction and trust baseline. The next slice should focus on decision → truthful provider result → next item → verified queue completion, not reopen explanation hierarchy or invent batch mutation.
