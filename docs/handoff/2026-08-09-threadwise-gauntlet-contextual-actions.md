# Threadwise Gauntlet handoff: contextual actions

Status: Slice complete; third fresh critic WIN
Current as of: 2026-08-09
Issue: `#107`
Parent: `#104`
Branch: `codex/threadwise-gauntlet`

## Outcome

The Threadwise companion now exposes one compact contextual `Actions` surface only when the exact selected object and lifecycle state have safe secondary actions. The current primary action stays inline, and `Change label` / `Change` remains one click away. Loading, applying, onboarding, Home, minimized, and actionless blocked states render no stale or invented menu.

The action surface is not a Gmail toolbar or global command palette. It reuses existing companion handlers, remains inside the provider-neutral overlay, and adds no capability or mailbox action.

## Files

- `extensions/gmail_companion/context_actions.js`
- `extensions/gmail_companion/manifest.json`
- `extensions/gmail_companion/content.js`
- `tests/gmail_companion_context_actions_test.js`
- `scripts/validate_threadwise_context_actions_cdp.mjs`

No provider adapter, backend route, analytics schema, SDK, service, dependency, credential flow, or mailbox-write path changed.

## Interaction policy

- The pure frozen registry returns at most four unique, allowlisted actions for the exact workspace mode.
- Review keeps Accept/apply and `Change label` inline; Open email and queue Back are contextual.
- Handled receipts keep `Looks right · Next` and `Change` inline; Open and Why are contextual.
- Teaching, correction, safety, and receipt states expose only the existing secondary actions listed by issue `#107`.
- `.` opens only from a non-interactive target already inside Threadwise. Menu arrows, Home/End, Enter/Space, and Escape receive priority only while open.
- Queue J/K is consumed while the menu is open and resumes through the current queue-navigation surface immediately after close.
- Every render invalidates the previous action generation. A stale detached action cannot revive an earlier state or issue a request.

## Gauntlet rounds

1. Fresh critic: **NOT WIN at `78/100`**, about `+8` over baseline, three of six tasks. Largest gap: the validator preserved only page scroll on a short receipt and did not close the loop on post-close J/K, same-state focus, keyboard state transition, or stale actions.
2. Fresh critic after root-level non-flow popover and strict continuity proof: **NOT WIN at `83/100`**, about `+13`, five of six tasks. Largest gap: the short-viewport popover overlapped Accept and obscured the one-click correction.
3. Fresh critic after collision-aware placement and hit testing: **WIN at `94/100`**, approximately `+24` over the documented `~70/100` baseline, six of six tasks, no hard gate.

True blind A/B was not practical because the controlled validator is candidate-specific. Critics compared the documented baseline hierarchy and pre-slice source with the candidate's real pixels and traces.

## Validation

- `node tests/gmail_companion_context_actions_test.js`: pass
- `node tests/gmail_companion_queue_navigation_test.js`: pass
- `node scripts/validate_threadwise_context_actions_cdp.mjs`: pass
- 30 real screenshots across `1280x800`, `756x469`, and `360x800`: contained
- nonzero Gmail-page scroll `180` and companion scroll `72`: preserved through open, roving, close, Why, Space, and a keyboard-only state transition
- queue J/K after menu Escape: pass through `activeElement`
- stale action deliberately reattached after context change: rejected; no state change or request
- review menu intersection with Accept / Change label at `756x469` and `360x800`: `0`
- Change label center hit test and exact single transition into change state: pass
- recorded requests: `27` allowed state-read/observer analytics; `0` unexpected
- `python3 -m unittest discover -s tests`: `795` passed
- JavaScript syntax, `git diff --check`, and focused policy tests: pass

Reproducible evidence:

- `/tmp/threadwise-context-actions/context-actions-trace.json`
- `/tmp/threadwise-context-actions/round3-final-validator-output.json`
- `/tmp/threadwise-context-actions/review-open-756x469.png`
- `/tmp/threadwise-context-actions/review-open-360x800.png`
- remaining state/view screenshots under `/tmp/threadwise-context-actions/`

## Safety and residual risk

- no live inbox, private email, credential, OAuth, provider search, or write access
- no compose, draft, reply, forward, send, auto-response, or AI email writing
- no new destructive or broad mailbox action
- the short-viewport top fallback temporarily covers the companion's Minimize control while the transient menu is open; the final critic judged this an acceptable contained popover tradeoff because Escape closes it, host Gmail remains untouched, and primary/correction actions remain reachable

## Next bounded step

Triage slice 4, selected-email explanation and one-click correction. It should attach classification, queue reason, matched evidence, and uncertainty more tightly to the current email while keeping the existing correction entry point and action-panel hierarchy intact.
