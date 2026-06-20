# Title

Add financial-account retrieval and tighten account/social classification

## Type

HITL

## User-visible goal

Reduce repeated review corrections by recognizing recurring finance/account mail and separating LinkedIn direct-person messages from generic low-value social noise.

## Scope

- Add one new retrieval label for finance/account-document style messages:
  - internal: `financial-account`
  - Gmail label: `EA/Finance`
- Improve account-access detection for:
  - password resets
  - reset-password flows
  - single-use codes
  - verification codes
  - similar account-access messages
- Add a safeguard so LinkedIn direct-person message digests bias to `personal` rather than `spam-low-value`
- Reclassify pending stored batches through the existing stored-batch rebuild path without forcing re-review of already reviewed items
- Keep the slice local-first; do not add any new Gmail mutation behavior

## Non-goals

- A broad finance taxonomy
- Automatic unsubscribe actions
- Replay/apply-live execution
- New inbox-removal policy behavior

## Acceptance criteria

- Pending finance-like messages such as Sun Life and MBNA statement notices can surface `EA/Finance`
- Password-reset and code-based account-access emails surface `EA/Account`
- LinkedIn direct-person message digests surface `EA/Personal` instead of `EA/LowValue`
- Existing reviewed items remain frozen, but pending stored batches can pick up the improved suggestions

## Expected tests or verification

- Test finance-like statements classify to `financial-account`
- Test password reset and single-use code messages classify to `account-security`
- Test LinkedIn direct-message digests classify to `personal`
- Run the relevant classifier, live-review, stored-batch, and browser-review test suites
