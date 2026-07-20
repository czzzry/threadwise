# Gmail Companion Acceptance Baseline

Status: Complete; requested review and recategorization paths repaired and verified
Current as of: 2026-07-12
Data classification: Sanitized operational summary. Personal names, message subjects, account identifiers, provider relationships, and exact mailbox counts have been removed or generalized.
Surface: Installed Threadwise Gmail companion in a locally signed-in browser profile

## Scope

This pass exercised review, categorization, teaching, and selected-email behavior through the visible Gmail and Threadwise interfaces. Dashboard and unsubscribe flows were excluded. No backend endpoint was used as a substitute for a user action.

The underlying acceptance run used private local inbox data. This public record keeps only the product behavior, defects, repairs, and aggregate proof needed to understand the work.

## Sanitized scenario ledger

| Scenario | Starting state | Attempted action | Result |
| --- | --- | --- | --- |
| Shipment update | Needs review; no confident category | Select `Orders`; apply to current email | Saved locally; provider write initially unconfirmed |
| Requested learning resource | Needs review; no confident category | Conversational correction to `Newsletter` | Preview succeeded after the interpretation path was repaired |
| Newly selected unsynced message | Opened directly in Gmail | Wait for Threadwise to recognize it | Initially remained on Home; later repaired with a visible sync path |
| Financial statement | Provider label and local snapshot disagreed | Current-only, future rule, and matching-inbox scopes | Provider-visible label became authoritative and the bounded broader apply succeeded |
| Related account notice | Included in a confirmed match set | Apply to reviewed matches | Correct label verified while preserving Inbox |
| Newsletter requiring a conditional reply | Needs review | Long instruction plus refinement | Conditional category language no longer creates a false conflict |

## Baseline results

### Passed

- Threadwise installed as an unpacked extension and injected its visible launcher into Gmail.
- Home showed the outstanding review count and a primary review action.
- Manual label selection exposed the expected categories.
- Preview copy clearly distinguished current-email, future-rule, and broader-match scopes.
- Conflicting corrections were blocked rather than silently applied.
- Minimizing Threadwise restored unobstructed inbox interaction.

### Failed or blocked

1. Current-email provider writes were not initially confirmed.
2. Natural-language conflict detection mishandled negation and conditional context.
3. The review queue did not advance reliably after a local-save/provider-write failure.
4. Selecting an arbitrary Gmail email did not initially update Threadwise.
5. The expanded panel blocked interaction with inbox content behind it.

## Repairs verified

- The minimized launcher now follows the Gmail message currently open.
- Unsynced messages expose a clear `Run Gmail sync` recovery action.
- Synced handled messages show their current classification instead of returning Home.
- Stale review summaries no longer expose a dead `Review next` action.
- Teaching conflict detection respects negation and conditional clauses.
- Provider label updates skip empty no-op mutations.
- Manual and conversational corrections share the same explicit scope model.
- Successful broad applies keep a durable completion receipt after refresh.
- Gmail-run requests use a bounded timeout long enough to return the final receipt.

## Validation

- Focused Gmail companion and analytics suites passed.
- The full repository suite passed with 606 tests at the time of the acceptance run.
- Browser verification passed for Home recovery, unsynced-message recognition, sync failure explanation, and synced-message recognition.
- Provider write-back was verified for current-only, future-rule, and explicitly included broader-match paths.
- No delete, trash, send, reply, autonomous unsubscribe, or broad archive action was introduced.

## Portfolio interpretation

This acceptance pass demonstrates a product-development loop rather than a claim of perfect inbox autonomy: observe the real interaction, identify the broken state boundary, protect the intended behavior with tests, repair it, and verify the visible outcome while preserving explicit mutation gates.
