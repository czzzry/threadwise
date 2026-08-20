# Always Label Successfully Processed Mail

Status: Current founder-approved decision
Current as of: 2026-08-20
Supersedes: the review-only model-write restriction in issue `#141` and the medium/high-only Proton write gate

## Decision

Every email that completes Threadwise classification receives the classifier's best one-to-three labels in the provider. Confidence controls whether the decision remains prominent for review; it does not decide whether the email is labeled.

The shared flow is:

1. Apply a learned or deterministic rule when one matches.
2. Otherwise ask the configured model for the best one-to-three labels using the email context.
3. Add those labels in Gmail or Proton Mail while preserving Inbox.
4. Keep uncertain decisions pending in the shared review experience so the user can correct or teach Threadwise.

## Queue Boundary

- A read-only coverage check may discover mail that has not completed classification. It requests a normal provider sync and must not create an unlabeled review item.
- Legacy read-only discovery records are ignored by runtime and selected-email queues. They remain on disk for audit history.
- A model or provider failure is an operational exception. It must be reported as such and must not appear as an ordinary unlabeled decision for the user to classify from scratch.
- A user may still explicitly reject all Threadwise labels during review. That is a deliberate reviewed outcome, not an automatic low-confidence fallback.

## Safety Boundary

This decision authorizes additive Threadwise label writes only. It does not authorize delete, Trash, Spam, send, unsubscribe, broad archive, provider rules, Proton label replacement, or Proton folder movement. Every provider write remains auditable and must preserve Inbox unless a separately approved Gmail rule applies.
