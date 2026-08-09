# Threadwise Gauntlet Slice Map

Status: Current decomposition; only an individually triaged issue is approved for implementation
Current as of: 2026-08-09
Parent PRD: `docs/prd-threadwise-gauntlet-2026-08-09.md`

Each slice is a thin, demoable path. The Sol helm selects and triages one slice at a time. Each important slice receives a fresh-context Luna builder and a separate fresh-context Luna critic. The critic inspects the real output, names the single largest remaining gap, and either sends that gap into a bounded correction round or declares the slice a win against the applicable bar.

## Slices

1. **First-run value inside the companion**
   - Type: AFK
   - Blocked by: None
   - Current issue: `#105`
   - Status: Complete; second fresh critic WIN at `97/100`
   - Outcome: On explicit first open, a provider-aware onboarding surface appears inside the existing minimized-by-default companion, uses the real logo, offers skip, persists completion, makes truthful safety claims, and hands off into a real Home or safe review state without credentials or writes.

2. **Queue-local search and keyboard navigation**
   - Type: AFK
   - Blocked by: Slice 1 only for shared interaction vocabulary
   - Current issue: `#106`
   - Status: Complete; fourth fresh critic WIN at `85/100` versus `~70/100` baseline
   - Outcome: Filter the loaded provider-scoped review queue by sender, subject, label, or status; navigate with panel-scoped keys; Enter runs the primary action; Escape retreats; Gmail typing and shortcuts remain untouched.

3. **Contextual action panel**
   - Type: AFK
   - Blocked by: Slice 2
   - Current issue: `#107`
   - Status: Complete; third fresh critic WIN at `94/100` versus `~70/100` baseline
   - Outcome: One Raycast-style action entry point exposes only the actions valid for the current selected email, queue item, teaching preview, receipt, or blocked state, with visible shortcuts and no global AI chat.

4. **Selected-email explanation and one-click correction**
   - Type: AFK
   - Blocked by: Slice 3
   - Current issue: `#108`
   - Status: Complete; first fresh critic WIN at `87/100` versus `~70/100` baseline
   - Outcome: Classification, queue reason, matched evidence, uncertainty, and the single correction entry point are attached to the selected email with deeper detail progressively disclosed.

5. **High-throughput review completion**
   - Type: AFK
   - Blocked by: Slice 2
   - Current issue: `#109`
   - Status: Implemented and paused for founder review; final fresh critic `PASS_NOT_WIN` at `82/100` versus `~70/100`, five of six tasks won
   - Outcome: Review → decision → background provider result → truthful receipt → next item → verified queue-complete state is fast, keyboard reachable, and never offers a nonexistent next item.
   - Remaining bounded gap: late teach-apply and handled-acknowledgement callbacks need the same direct live-host anchor guard now protecting completion-state responses.

6. **Bounded batch triage preview**
   - Type: AFK
   - Blocked by: Slices 4 and 5
   - Outcome: Select a small set of unresolved items, preview exact scope and count, cancel safely, and apply only through existing approved bounded paths. No delete, archive, Trash, Spam, send, or implicit broad mutation.

7. **Truthful zero and freshness states**
   - Type: AFK
   - Blocked by: Slice 5
   - Outcome: Distinguish verified provider Inbox zero, no Threadwise-reviewable items, stale sync, unavailable sync, unsynced mail, and unresolved items remaining.

8. **Compact Home and activity hierarchy**
   - Type: AFK
   - Blocked by: Slices 3 and 7
   - Outcome: Home answers “what should I do next?” in one viewport; reports, analytics, retries, and technical detail remain available behind explicit progressive disclosure.

9. **Compact Threadwise settings and help**
   - Type: AFK
   - Blocked by: Slices 2 and 8
   - Outcome: Configure Threadwise density, explanation visibility, onboarding replay, and keyboard help without duplicating Gmail settings or creating a dashboard-first product.

10. **Contextual unsubscribe triage**
    - Type: AFK
    - Blocked by: Slices 3 and 4
    - Outcome: Relevant messages expose a quiet unsubscribe entry point, exact supported/manual route, explicit confirmation, and truthful receipt while preserving the current execution boundary.

11. **Containment, accessibility, and performance hardening**
    - Type: AFK
    - Blocked by: Runs continuously; final consolidation after Slices 1–10
    - Outcome: Compact, expanded-review, and narrow viewports preserve Gmail; focus, live regions, reduced motion, response budgets, capped queues, and refresh behavior meet production acceptance.

12. **Pure unpacked-extension acceptance and provider parity closeout**
    - Type: HITL for final live verification; AFK for synthetic parity work
    - Blocked by: All shared interaction slices being claimed complete
    - Outcome: The real unpacked extension proves the shared interaction on controlled Gmail and Proton pages; the remaining live Proton selected-message check stays separately approval-gated before legacy-console removal.

## Excluded Zero Capabilities

- compose, reply, forward, drafts, send, and AI writing
- unified inbox and a replacement email-client shell
- duplicating Gmail archive, snooze, folder navigation, or general mailbox search
- destructive or broad provider actions outside existing approved Threadwise boundaries

## Fixed Critic Gate

- Hard fail if the real logo changes, the product leaves the Gmail overlay, any email-writing behavior appears, or a mailbox change lacks explicit scope and truthful receipt.
- Pass at 80/100 or higher with no hard fail and no zero score on a core criterion.
- A/B win requires a passing challenger, at least a ten-point improvement, at least four of six fixed tasks won, and no safety or host-footprint regression.
