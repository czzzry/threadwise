# Status

Implemented on 2026-06-23
Current as of: 2026-06-23
Triage state: `implemented`
Builds on: `docs/prd.md`
Blocked by: None

# Title

Classify LinkedIn jobs-noreply job recommendations

## Type

AFK

## User-visible goal

Reduce a recurring reviewed unlabeled Gmail exception family by classifying LinkedIn `jobs-noreply@linkedin.com` recommendation mail like `apply now to …` and `apply to … and more` into `job-related`.

## Scope

- Tighten the local classifier only
- Cover recurring LinkedIn `jobs-noreply@linkedin.com` recommendation patterns already seen in stored batches
- Keep the slice inside the existing `job-related` taxonomy
- Preserve current handling for LinkedIn application-status and saved-job-expiry mail

## Non-goals

- Broader LinkedIn policy redesign
- New labels or taxonomy expansion
- Gmail mutation behavior changes
- Solving every remaining unlabeled sender family

## Acceptance criteria

- LinkedIn `jobs-noreply@linkedin.com` mail with subjects like `Alex, apply now to ‘AI Product Manager at Quectel’` classifies to `job-related`.
- LinkedIn `jobs-noreply@linkedin.com` mail with subjects like `Alex, apply to Product Manager at Scrive and more` classifies to `job-related`.
- Existing saved-job-expiry and application-status behavior continues to work.
- The slice does not broaden Gmail mutation scope.

## Expected tests or verification

- Add classifier tests for the two recurring `jobs-noreply@linkedin.com` recommendation patterns.
- Re-run the classifier suite.
- Re-run the unlabeled exception inspection command and confirm the recurring jobs-noreply clusters are reduced.
