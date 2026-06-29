Status: Current evaluation contract
Current as of: 2026-06-28
Owner slice: `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`
Builds on: `docs/prd.md`, `docs/issues/056-read-only-two-inbox-shadow-classifier-evaluation.md`
Scope: This note defines what the current stored corpora are allowed to prove. It does not define runtime classification behavior.

# Purpose

This note exists so later agents can tell which evidence buckets are safe to tune on, which ones are only for regression or internal checks, and which claims would overstate what the repo currently proves.

# Global Rules

## 1. Keep reviewed and shadow evidence separate

- Gmail reviewed history is benchmark evidence.
- ProtonMail and Hotmail are shadow evidence.
- Do not combine them into one headline quality score without preserving the distinction.

## 2. Tune only from discovery families

- Discovery is the only shadow bucket that may directly drive accepted memory, candidate review, or new deterministic rules.
- Validation and holdout are for post-tuning checks only.

## 3. Split shadow corpora by family, not by individual message

- The split unit is normalized sender plus normalized subject family.
- Repeated messages from the same family must stay together so the same pattern does not leak across discovery and holdout.

## 4. Contamination is explicit, not implied away

- If a validation or holdout family is directly inspected for tuning, founder review, or product-design reasons, that family is contaminated.
- Once contaminated, move it into discovery in later reports or regenerate the split before claiming fresh evidence.

## 5. Shadow corpora are internal evidence, not publication-grade proof

- ProtonMail and Hotmail can support strong internal product decisions.
- They should not be described as pristine untouched final exams.

# Corpus Contract

## Gmail reviewed history

- Provider: `gmail`
- Kind: reviewed benchmark
- Trust level: medium
- Contamination status: training-adjacent
- Allowed uses:
  - regression checks against reviewed `final_labels`
  - label-distribution sanity checks
  - measuring whether memory or rule projections preserve reviewed Gmail behavior
- Disallowed uses:
  - claiming a pristine unseen test set
  - claiming out-of-distribution generalization

Reason:
Many current Gmail rules were authored from this history. It is still the best reviewed regression benchmark in the repo, but it is not untouched holdout evidence.

## Gmail unreviewed stored tail

- Provider: `gmail`
- Kind: shadow tail
- Trust level: low
- Contamination status: mixed history
- Allowed uses:
  - local projection
  - spotting recurring misses that still exist in stored Gmail history
- Disallowed uses:
  - claiming reviewed benchmark quality
  - claiming unseen generalization

Reason:
These items help with local diagnosis, but they are neither reviewed benchmark evidence nor a clean shadow corpus.

## ProtonMail shadow corpus

- Provider: `protonmail`
- Kind: shadow corpus
- Trust level: medium
- Contamination status: partially exposed pre-split
- Allowed uses:
  - discovery-family review
  - candidate memory and rule design from discovery families
  - internal validation and holdout checks after discovery tuning
- Disallowed uses:
  - claiming ground truth without review
  - claiming a pristine final generalization exam

Reason:
The first read-only ProtonMail run surfaced the full unlabeled exception list before the current family split existed. That means ProtonMail remains highly useful shadow evidence, but its validation and holdout buckets are internal checks, not untouched final proof.

## Hotmail / Outlook shadow corpus

- Provider: `outlookmail`
- Kind: shadow corpus
- Trust level: medium
- Contamination status: debug-inspected
- Allowed uses:
  - large out-of-distribution miss discovery
  - family-level review and suggestion generation
  - internal validation and holdout checks with explicit contamination notes
- Disallowed uses:
  - claiming a pristine untouched holdout
  - claiming publication-grade benchmark purity

Reason:
The Hotmail corpus was used to debug browser-backed ingestion and inspect aggregate behavior while recovering the full unread set. It is a strong shadow corpus, but not a never-seen final exam.

# Split Policy

- Split unit: normalized sender plus normalized subject family
- Default shares:
  - discovery: `50%`
  - validation: `25%`
  - holdout: `25%`
- Exposed-family rule:
  - Any family already surfaced to the founder or to a tuning workflow must be forced into discovery before later validation or holdout claims are made.

# Claim Language

Use language like:

- "Reviewed Gmail benchmark stayed stable."
- "ProtonMail shadow unlabeled rate improved on validation and holdout."
- "Hotmail remains a strong but contaminated shadow corpus."

Avoid language like:

- "The classifier now generalizes universally."
- "Hotmail proves final accuracy."
- "ProtonMail holdout is a pristine test set."
