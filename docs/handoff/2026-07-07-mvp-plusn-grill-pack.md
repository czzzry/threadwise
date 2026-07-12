# MVP+N Grill Pack: Teach/Label Loop Before Write-Through Coding

## Scope lock for next sprint
- Goal: stabilize the **teach flow** before touching more UI/aesthetic changes.
- Assumptions to confirm:
  1. A rule change should always have one of 3 scoped outcomes:
     - `apply this email only`
     - `apply this email and save for future`
     - `apply this email, save for future, and backfill matching inbox items`
  2. Rule acceptance is the primary source of truth for what action will happen; UI copy and state must make this unambiguous.
  3. Inbox visibility should reflect applied rules after a successful backfill/inbox sync cycle.

## Locked product contract
- The teach loop is:
  1. user drafts intent
  2. Threadwise proposes a plain-English rule
  3. user accepts or edits the proposed rule
  4. user chooses scope
  5. Threadwise applies the action
  6. Threadwise shows a compact receipt
- Rule definition and scope selection are separate states in the UI.
- The accepted rule is the source of truth for execution.
- Gmail write-through is the intended operational model, not local preview-only behavior.

## What to grill now (pre-rate-limit)
1. Rule grammar
   - What can a user say to define intent in one shot?
   - Which inputs should be treated as label changes vs category/priority changes?
   - How do we expose uncertainty in the rule interpretation before apply?

2. Scope semantics
   - Confirm exact meaning of the three scope buttons.
   - Confirm whether “future + inbox” includes only already-seen local batch items or full Gmail search scope.
     - Decision: full Gmail search/backfill for launch.
   - Confirm whether manual reload is required between teach and mailbox update.
   - Decision:
     - `Fix email`: apply only to the current email.
     - `Fix + future`: apply to the current email and save the rule for future matching emails.
     - `Fix + inbox`: apply to the current email, save the rule for future matching emails, and backfill all matching existing inbox emails.

3. Result states
   - What is the minimum visible state after each apply:
     - in-progress (spinner/disabled state),
     - success summary,
     - partial success (some writes failed),
     - no-op (nothing changed because it already matched),
     - hard failure with actionable guidance.
   - Whether a second click is allowed while running.
   - Decision:
     - Running state is explicit with spinner/disabled CTAs.
     - Success receipt is compact and concrete.
     - Partial success distinguishes current email, future rule, and inbox backfill outcomes.
     - Failure keeps the rule text intact for retry.
     - No generic detail drawers by default.

4. Home mode / selected email
   - What should be shown when opening TW with no email selected?
   - When should “last reviewed email” be shown, if at all?
   - How do we avoid stale context reloading from old local batches?
   - Decision:
     - If no email is actively selected, show a minimal empty home state.
     - Never preload a previously reviewed email into agent view.

5. Safety rails
   - Should rule changes be reversible (undo/rollback) for this slice?
   - What guardrails prevent broad auto-apply to the wrong class (e.g. wrong labels)?
   - What confidence threshold is required to auto-run broad actions?
   - Decision:
     - No undo in this slice.
     - This flow does not delete/archive mail.
     - Large inbox runs require confirmation.

6. Inbox write-through contract
   - Can this run incrementally (just touched matches) or must it be full mailbox scan?
   - Should backfill happen on-demand by rule action only, or periodic background sync?
   - How should failures in live writes be surfaced in the sidebar and simulator?
   - Decision:
     - `Fix + inbox` uses the accepted rule as the match definition, not vague similarity.
     - Backfill is full inbox search/write-through.
     - Estimated match count is shown before execution.
     - `0-25` matches: run immediately.
     - `26-200` matches: show estimate, still one-click run.
     - `200+` matches: require inline confirmation before apply.
     - Save the rule even if inbox backfill partially fails.

7. Acceptance criteria wording
   - Exact wording for scope buttons and post-action text to match user mental model:
     - `Fix email`
     - `Fix + future`
     - `Fix + inbox`
   - Define wording for completed states so user can tell if Gmail changed.
   - Decision:
     - Scope helper text:
       - `Applies only to this email.`
       - `Applies to this email and future matching emails.`
       - `Applies to this email, future matches, and matching emails already in your inbox.`
     - Receipt titles:
       - `Rule applied`
       - `Partially applied`
       - `Could not apply rule`

## Locked teach-state UI
- Draft state:
  - one input for user intent
- Proposal state:
  - label: `Proposed rule:`
  - actions: `Edit`, `Looks right`
- Edit behavior:
  - the user edits the proposed rule itself, not a separate hint
  - if the edited rule clearly states which emails it applies to and what should happen, accept it directly
  - if the edited rule is ambiguous, reformulate once and ask for confirmation
  - confirmation CTA after editing: `Use this rule`
- Accepted rule state:
  - show the accepted rule as a stable block
  - then show scope actions underneath
  - after execution, replace the accepted-rule block with the receipt

## Locked home and receipt UI
- Home empty state copy:
  - `No email selected`
  - `Open an email to review or teach a rule.`
- Receipt should stay compact.
- Show recovery-relevant inline status only:
  - `Email: done`
  - `Future rule: done`
  - `Inbox: failed`
- Preserve teach input until full success or explicit user clear.

## Mature-product hardening checks to run after write-through works
- Regression: creating a rule never leaves “stale email loaded” when no message is open.
- Correctness: existing Gmail rule examples (`LinkedIn jobs`, `Recruiter outreach`, `receipts`) should apply consistently to future and backfilled items.
- Idempotency: repeating the same action does not duplicate labels or duplicate queue entries.
- Recovery: failed Gmail writes are retried or clearly marked and removable without losing the local teaching data.
- Performance: full backfill does not freeze UI; progress updates remain responsive.
- Auditability: user can see what rule changed, when, and what it touched (counts + labels).

## Decision package to finalize before implementation
- [x] Exact rule scope wording accepted.
- [x] Exactly one default action path per scope chosen for button + shortcut mapping.
- [x] Backfill definition fixed (full-inbox confirmed).
- [x] “This email” selection reset policy locked.
- [x] Success/failure copy and “worked” signal finalized.
- [x] Failure handling policy for live Gmail write errors finalized.
- [ ] Bulk-run confirmation UI copy finalized.
- [ ] Match-count estimation UX finalized.
- [ ] Implementation slice breakdown converted into issues/tasks.

## Execution order when coding resumes
1. Implement teach-write-through in backend path and explicit scope contract.
2. Make UI state machine deterministic and minimal (one active state at a time).
3. Add post-action feedback with explicit counts + touched-labels.
4. Add no-stale-home-mode rule and clear “empty home” behavior.
5. Run a local/live validation matrix for each scope action.

## Residual uncertainty to keep visible
- Full-inbox backfill in MVP+N is now confirmed.
- Whether one shared “smart” scope is needed or keep fixed scope buttons only.
- Whether to show raw Gmail write IDs / history in UI or keep it abstracted.
- How conservative the first rule matcher should be for ambiguous rule language.
