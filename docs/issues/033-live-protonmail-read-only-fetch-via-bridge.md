# Title

Live ProtonMail read-only fetch via Bridge

## Type

HITL

## User-visible goal

Fetch a bounded batch of messages from one live ProtonMail inbox into the existing provider-aware local batch model using Proton Mail Bridge, without performing any write or inbox-mutation actions on the Proton account.

## Scope

- Add a live ProtonMail read-only fetch path for one account
- Use Proton Mail Bridge as the provider edge
- Read only from `INBOX`
- Persist fetched ProtonMail messages into the existing stored batch model
- Reuse the current classification and reporting workflow once messages are in the local batch format
- Keep the slice read-only at the provider edge

## Non-goals

- ProtonMail label write-back
- ProtonMail inbox mutation
- ProtonMail unsubscribe execution
- Cross-inbox combined runs
- Broad provider abstraction work beyond this fetch seam
- Web automation against the Proton Mail UI

## Acceptance criteria

- One bounded live ProtonMail fetch command can import a local batch for one account through Bridge
- Imported live ProtonMail batches use the same stored batch shape as Gmail where practical
- Imported live ProtonMail batches retain explicit provider metadata
- Existing local inspection and reporting tools can read the imported ProtonMail batch without Gmail-specific assumptions
- The live ProtonMail fetch path performs no provider write actions

## Expected tests or verification

- Test Bridge config loading and read-only IMAP fetch behavior
- Test live ProtonMail fetch persists a provider-aware stored batch
- Test live ProtonMail fetch performs no provider write methods
- Re-run the relevant Proton fetch, batch summary, and report-related suites
