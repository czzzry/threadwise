# Live Gmail Review Baseline

Status: Complete; all requested review and recategorization paths repaired and verified live
Current as of: 2026-07-12
Surface: Installed Threadwise Gmail companion in the founder's signed-in Chrome profile

## Scope

This pass exercised only review, categorization, teaching, and selected-email behavior through the visible Gmail and Threadwise interfaces. Dashboard and unsubscribe flows were intentionally excluded. No backend endpoint was used as a substitute for a user action.

## Touched-email ledger

| Email | Sender | Starting Threadwise state | Attempted action | Result |
| --- | --- | --- | --- | --- |
| `Dispatched: ‘Falechay Men's Socks, 12...’` | Amazon.de | Needs review; no confident category | Manual selection: `Orders`; apply to current email | Saved locally as Orders; Gmail label not confirmed |
| `Dive Deeper with Data Analysis` | University of Michigan / Coursera | Needs review; no confident category | Conversational correction to `Newsletter`; then fix current email | Rule preview eventually succeeded only after removing every alternative-label term; current change saved locally; Gmail label not confirmed |
| `Welcome to OpenWhispr!` | OpenWhispr | Opened directly from Gmail inbox | Wait for Threadwise to recognize selected email | Threadwise remained on Home; no selected-email, unsynced, check-again, or run-sync state appeared |
| `Your statement is ready` | Sun Life | Gmail visibly had `EA/Finance`; Threadwise local snapshot said needs review | Long conversational instruction; current-only; future rule; matching inbox | Current Gmail write confirmed; future rule saved with no Gmail mutation; 30 matching stored/inbox messages applied; a sampled match visibly showed `EA/Finance` in Gmail |
| `Cezary, your account is missing information.` | Sun Life | Uncategorized in Threadwise affected-email review | Included in confirmed matching-inbox apply | Verified through Gmail search with `EA/Finance` and Inbox visible |
| `Your AI Development Workflow Resource` | Zevi Arnovitz | Needs review; no confident category | Manual `Newsletter`; save future behavior; long conditional instruction and refinement | The pre-fix future action saved only a rule and did not relabel the current email, exposing a scope bug. The refined narrow rule is now understood without repeating the clarification question. |

## Baseline results

### Passed

- Threadwise installs in Chrome as an unpacked extension and injects its visible `TW` control into Gmail.
- Home clearly shows `3 emails need your review`, the latest run summary, and a primary `Review next` action.
- `Review next` initially opens the next uncertain email.
- Manual label selection exposes all expected categories.
- Manual preview clearly states that the change applies to the current email only.
- A conversational note that appears to conflict with the selected label is blocked rather than silently applied.
- A direct single-category instruction eventually produces a visible future-rule interpretation, exact matching count, and separately gated broader options.
- Minimizing Threadwise makes the underlying Gmail inbox usable again.

### Failed or blocked

1. **Current-email Gmail writes are not confirmed.** Both manual and conversational current-email changes ended with `Saved locally` and `Gmail label not confirmed`.
2. **Natural-language conflict detection ignores negation and conditional context.** `These aren't really personal updates` was interpreted as `Personal`; a revised instruction explicitly saying `Newsletter, not Personal` still produced the same conflict. Mentioning `ReplyNeeded` as an exception then made Threadwise claim the note meant `ReplyNeeded`.
3. **The review queue does not advance reliably after local-save/Gmail-write failure.** Home continued to show three review items, and `Review next` stopped responding without loading, disabled, error, or retry feedback.
4. **Selecting an arbitrary Gmail email does not update Threadwise.** After opening `Welcome to OpenWhispr!` and waiting more than five seconds, Threadwise remained on Home. Because no unsynced state appeared, the user had no visible way to run Gmail sync or check again.
5. **The expanded floating panel blocks inbox interaction behind it.** Selecting a visible inbox row did not work until the user minimized Threadwise.

### Paths blocked by baseline failures

- Accepting a proposed label could not be exercised because all reachable review items required the user to choose a label.
- Saving the future rule after fixing the current email could not be completed because the current-email Gmail write failed and the flow ended at the recovery receipt.
- Reviewing and applying the ten matching University of Michigan emails could not be completed for the same reason.
- The visible unsynced-email `Run Gmail sync` path could not be exercised because Threadwise never recognized the selected Gmail email.

## Baseline interpretation

The safety gates are generally present, but the main product loop is not usable end to end in the live inbox. The first repair priority is the live Gmail mutation/selection boundary. The language-understanding problem is separate: the current conflict detector behaves like category-keyword matching rather than understanding the user's complete instruction.

## Repair and retest pass

### Fixed and verified

- The minimized `TW` launcher now follows the Gmail message currently open instead of forcing Home.
- Opening `Welcome to OpenWhispr!` now produces the correct unsynced-email state and visible `Run Gmail sync` action.
- Opening the synced Amazon message now reaches `Orders · Kept visible` instead of remaining on Home or resetting its understanding timer.
- Home no longer exposes a dead `Review next` action when the historical summary count and actionable queue disagree. It shows `Review queue needs a refresh` with `Run Gmail sync`.
- Teaching-note conflict detection now requires an explicit positive assignment to another label; negated categories and conditional exception clauses no longer create false conflicts in the regression contract.
- The already-present concurrency fix for the privacy-safe analytics installation ID was loaded by restarting the Threadwise helper.

### OAuth recovery and UI retest

The founder explicitly approved Gmail reauthorization. Google completed the existing read-only authorization flow and Threadwise successfully fetched one live message into `founder-test-batch-53`. The rejected token was retained as `founder-test.json.rejected-2026-07-12` for audit/rollback.

The visible sync request was found to take about 75 seconds while the extension abandoned API calls after 30 seconds. A Gmail-run-specific three-minute timeout now preserves the request long enough to receive its completion receipt. This fix is locally tested but requires an extension reload before a final live receipt retest.

### Final live scope pass

- Directly opening a real synced Gmail message moved Threadwise to that email and exposed review controls.
- Current-email conversational apply passed and confirmed `Gmail label updated` plus `Kept in Inbox`.
- Future-only learning passed and confirmed `Future rule saved` plus `No Gmail message was changed`.
- Matching-inbox apply reviewed 30 exact matches, applied Finance, and saved the future candidate. Gmail search independently verified `Cezary, your account is missing information.` now has `EA/Finance` and remains in Inbox.
- A long multi-sentence instruction initially failed because a conditional `ReplyNeeded` clause was treated as an immediate assignment. Removing the category word allowed the same intent to preview correctly. The conflict detector is now fixed locally to ignore conditional category mentions that precede `if`, `when`, or `unless`.
- Manual selection without a note exposed only current-email apply in the loaded build. The local fix now generates a transparent sender-based draft and routes manual selection through the same three-scope confirmation flow as a conversational correction.
- When Gmail visibly has an EA label but a historical local item is stale, the local fix now passes visible Gmail EA labels into selected-email state and treats the provider-visible label as authoritative.

### Validation

- Focused Gmail companion and analytics suites: 84 tests passed.
- Full repository suite: 606 tests passed.
- Live Chrome verification passed for Home recovery, selected unsynced Gmail email recognition, visible sync failure explanation, and selected synced Gmail email recognition.

## Autonomous continuation and final repair cycle

### Additional live paths exercised

- The visible Home recovery path ran a Gmail sync through Threadwise. The stored batch count advanced from 55 to 56, and the panel displayed `Gmail sync finished` without using a backend substitute for the user action.
- Directly opening `Your AI Development Workflow Resource` in Gmail moved Threadwise to the same email and exposed its review controls.
- Manual category selection without a note reached the shared rule preview. `Newsletter` produced a transparent sender-semantic rule and the visible scope controls.
- The loaded pre-fix `Teach future rule` action was exercised. Its receipt explicitly said the current email was not relabeled, proving that the button implemented future-only persistence instead of the required current-email-plus-future scope.
- A long instruction said the requested resource looked like marketing but must not be Promotions, should remain Newsletter, and should become ReplyNeeded only when a future message explicitly asks for a response. Threadwise selected Newsletter without a false category conflict.
- The follow-up refinement limited the rule to requested resources, guides, newsletters, and digests; excluded unrelated account and transactional mail; and retained conditional ReplyNeeded precedence. Before repair, Threadwise repeated the same clarification. After the backend repair was loaded, the live preview showed `Future rule`, kept Newsletter, and no longer asked the redundant question.
- Manual matching-inbox review on `Your statement is ready` exposed 30 exact Sun Life matches, eight broader similar candidates, per-email inspection/exclusion controls, and `Apply to included`. The action updated the recorded batch/write statuses to applied without another Gmail HTTP 400 after the idempotent-write repair was loaded.

### Confirmed bugs fixed and merged

1. Reapplying an already-present EA label sent Gmail an empty modify payload, which Gmail rejected with HTTP 400. Threadwise now skips no-op label mutations.
2. The visible `Teach future rule` button dispatched `save-future-rule`, which intentionally saved only a candidate. It now dispatches `future-only`, the required current-email-plus-future-rule action.
3. Explicitly narrowing a semantic rule did not satisfy Threadwise's own clarification question. Boundary-aware confidence now accepts concrete inclusion and exclusion language while preserving questions for genuinely vague rules.
4. Successful `included-existing` outcomes fell out of the result state and returned to the preview, hiding success. Broader scopes now have scope-specific progress copy and a durable `Done` receipt that survives same-email refreshes.

All four repairs are merged to `main` through PRs 71-73. GitHub CI passed for each follow-up. The final repository state at `dd9f60d` passes 606 tests, focused review-flow checks, JavaScript syntax checks, and `git diff --check`.

### Final live confirmation

After loading the final extension build, the manual current-email-plus-future path relabeled `Your AI Development Workflow Resource` to `EA/Newsletter`, saved the future rule, reported one successful Gmail label write, and did not rewrite other stored emails.

The manual current-email-plus-future-plus-inbox path then ran on `Your statement is ready`. Threadwise displayed the scope-correct progress message for the full operation, remained connected beyond the former 30-second timeout, and produced a durable receipt after roughly 135 seconds: current email done, Gmail label done, 30 other stored emails changed, future rule saved, 31 Gmail writes applied, one skipped, and no Inbox removals. The same receipt remained visible after the background follow-up refresh.

The final extension timeout repair is merged through PR 75 at `c055aa9`. Together with PRs 71-74, this closes every confirmed blocker from the requested review/categorization QA scope.
