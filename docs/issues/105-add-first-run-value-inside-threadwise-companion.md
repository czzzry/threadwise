# Issue 105: Add first-run value inside the Threadwise companion

Status: Completed; Gauntlet WIN at 97/100
Current as of: 2026-08-09
GitHub issue: `#105`
Parent: `#104`
Builds on: `docs/prd-threadwise-gauntlet-2026-08-09.md`

## Outcome

Add the first real Threadwise onboarding path inside the existing provider-aware companion. The companion still mounts minimized and remains closed until the user explicitly opens it. On first explicit open, one compact first-run surface detects the active provider, uses the existing Threadwise logo, explains the bounded triage value and no-email-writing boundary, offers skip, persists completion by onboarding version, and hands the user into the existing Home or safe review workflow using current Threadwise state.

The authoritative implementation contract and acceptance criteria are in the triage brief on GitHub issue `#105`.

## Completion evidence

- real provider-aware companion still mounts minimized and opens onboarding only after an explicit user action
- versioned completion and dismissal persist through `chrome.storage.local`
- selected-email, provider-scoped queue, Home, and offline/not-ready paths are exercised with synthetic browser state
- Enter activates the focused contextual primary action; the `756×469` and `360×800` layouts keep required content visible with a 44-pixel action target
- captured requests contain no provider sync, teaching apply, safety apply, unsubscribe execution, mailbox write, reply, or send call
- privacy-safe onboarding shown/completed/dismissed analytics use the existing observer-only PostHog path
- first independent critic: `79/100`, failed for short-viewport focus scrolling
- second fresh critic after the bounded correction: `97/100`, WIN

Handoff: `docs/handoff/2026-08-09-threadwise-gauntlet-onboarding.md`

## Boundaries

- no provider chooser
- no AI key, credential, OAuth, or provider setup
- no fake metrics, connection success, or schedule
- no separate setup application
- no provider sync or mailbox mutation
- no AI compose, draft, reply, forward, send, or auto-response
- preserve the existing Threadwise logo and provider-neutral companion architecture
