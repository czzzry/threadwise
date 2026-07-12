# Title

ProtonMail read-only fetch into provider-aware batch model

## Type

HITL

## User-visible goal

Fetch a bounded batch of messages from one ProtonMail inbox into the same local provider-aware batch model already used for Gmail, without taking any write actions on the ProtonMail account.

## Scope

- Add a ProtonMail read-only fetch path for one account
- Persist fetched ProtonMail messages into the existing stored batch model
- Mark stored ProtonMail batches with `provider = "protonmail"`
- Reuse the current classification and reporting workflow once messages are in the local batch format
- Keep the slice read-only at the provider edge

## Non-goals

- ProtonMail label write-back
- ProtonMail inbox mutation
- ProtonMail unsubscribe execution
- Cross-inbox combined runs
- Broad provider abstraction work beyond this fetch/import seam

## Acceptance criteria

- One bounded ProtonMail fetch command can import a local batch for one account
- Imported ProtonMail batches use the same stored batch shape as Gmail where practical
- Imported ProtonMail batches retain explicit provider metadata
- Existing local inspection and reporting tools can read the imported ProtonMail batch without Gmail-specific assumptions

## Expected tests or verification

- Test ProtonMail fetch persists a provider-aware stored batch
- Test imported ProtonMail batches can flow through existing local summary/report seams
- Re-run the relevant fetch, summary, and report-related suites
