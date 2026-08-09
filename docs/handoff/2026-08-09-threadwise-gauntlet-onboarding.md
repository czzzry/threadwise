# Threadwise Gauntlet: first-run companion onboarding

Status: Completed bounded slice
Current as of: 2026-08-09
Parent PRD: `docs/prd-threadwise-gauntlet-2026-08-09.md`
Issue: `#105`
Gauntlet result: WIN, second fresh critic `97/100`

## Outcome

Threadwise now introduces itself inside the real provider-aware companion instead of sending a new user to the detached onboarding prototype. The extension still mounts minimized. On the user's first explicit open, it uses the active provider and current product state, explains classification, labels, correction, broader-change previews, and the no-writing/no-send boundary, then offers one contextual next step plus `Skip intro`.

Completion and dismissal persist by onboarding version through `chrome.storage.local`. Continue enters the selected reviewable email first, then the next provider-scoped needs-attention item, then Home. A not-ready local companion stays in onboarding with truthful remediation and `Check again`; retry never marks the flow complete falsely.

## Implementation

- `extensions/gmail_companion/onboarding.js` owns versioned persistence and deterministic destination selection.
- `extensions/gmail_companion/content.js` owns the compact in-panel surface, explicit-open gate, focus behavior, handoffs, truthful recovery, and narrow/short-viewport containment.
- `extensions/gmail_companion/manifest.json` loads onboarding before the content script.
- `extensions/gmail_companion/analytics.js` and `src/product_analytics.py` add privacy-safe shown/completed/dismissed funnel events through the existing observer-only analytics path.
- `tests/gmail_companion_onboarding_test.js` covers storage and destination selection.
- `scripts/validate_threadwise_onboarding_cdp.mjs` drives the real content scripts inside a controlled synthetic Gmail-like host and records every product request.

## Gauntlet rounds

The prior real companion benchmark was `70/100`; the detached prototype benchmark was `17/100`.

Round one reached `79/100` and failed. The fresh critic's single largest gap was focus-induced scrolling at `756×469`: the primary action had focus, but the first viewport hid the Threadwise identity and headline.

The bounded correction used focus without scrolling, compact short-viewport rules, a contained mobile layout, and genuine Enter-key activation. A new fresh critic preferred the corrected desktop pixels blind, scored the result `97/100`, and declared WIN/PASS. The final synthetic run additionally closes that critic's one evidence caveat by exercising the offline/not-ready path.

## Validation

- `node --check` for onboarding, analytics, content, and the CDP validator
- provider-adapter, companion-analytics, and onboarding JavaScript tests
- `python3 -m unittest tests.test_product_analytics`: `14` passing tests
- focused companion/teaching regression set: `159` passing tests
- synthetic browser acceptance at `756×469` and `360×800`
- required identity, headline, explanation, status, and 44-pixel focused primary action visible together with `scrollTop = 0`
- Enter completes onboarding and opens selected review
- completed and dismissed state survives reload
- selected-email, provider queue, Home, and offline/not-ready handoffs pass
- final captured request set contains no provider/write-class request
- `git diff --check` passes

No live inbox, private email, credential, OAuth, provider client, or mailbox mutation was used.

## Risks and boundaries

- Browser acceptance is controlled and synthetic. A live unpacked-extension check remains separately approval-gated under the repo's sensitive-data policy.
- Bumping the onboarding version intentionally makes the new version unseen again.
- The detached `prototype/threadwise_onboarding_prototype.html` is historical hypothesis material and is not loaded by the extension.
- This slice does not add a provider chooser, account setup, AI key setup, metrics dashboard, schedule, compose, reply, or send behavior.

## Next bounded step

Triage the slice-map candidate for provider-scoped queue filtering plus panel-scoped keyboard navigation. Preserve Gmail typing/shortcut behavior and use a fresh builder and separate fresh critic before claiming that slice complete.
