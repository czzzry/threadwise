# Universal Threadwise Provider Parity Handoff

Status: Implementation complete; live Proton acceptance pending
Current as of: 2026-08-01
Source PRD: `docs/prd-universal-threadwise-experience-2026-08-01.md`
GitHub parent: `#96`

## Delivered

- One extension mounts the same minimized-by-default Threadwise panel on Gmail and Proton Mail.
- Proton selected-email context and provider navigation feed the shared sidebar contract.
- Gmail and Proton use the same review, natural-language teaching, full-context LLM review, force-LLM, scope preview, and apply controls.
- All provider-writing scopes advance to the next review item immediately and use serialized background workers.
- Provider writes remain additive, Inbox-preserving, read-back verified, visible in recent activity, and retryable without repeating the teaching conversation.
- Live Inbox reconciliation excludes deleted, moved, and already-completed Proton messages from broader matching and review counts.
- Shared PostHog events retain their existing names and add only a privacy-safe `provider` property.
- Proton daily-run output now opens Proton Mail directly rather than directing the founder to the separate review console.

## Verification

- Full repository test suite passes.
- JavaScript syntax checks pass for the extension content and background scripts.
- Python compilation checks pass for the changed provider and companion modules.
- Desktop and narrow-viewport synthetic browser checks pass without horizontal overflow or unusable controls.
- Tests prove full Proton message context reaches forced LLM review and rapid accepts are applied in order on both providers.

## Remaining Acceptance

1. Reload extension version `0.3.0` and open Proton Mail.
2. Confirm Threadwise mounts minimized, opens explicitly, follows one selected Proton email, and displays the provider-scoped queue.
3. With explicit approval, accept one low-risk Proton label and confirm immediate next-item navigation plus a verified background receipt.
4. After that succeeds, remove the `/proton-review` page and its legacy mutation routes, then close parity issue `#103` and parent `#96`.

No live Gmail or Proton mailbox read or write was performed during this implementation.
